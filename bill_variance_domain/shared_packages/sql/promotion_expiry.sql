WITH trade_in_promos AS (
    SELECT DISTINCT
        UPPER(TRIM(BCR.CPC_PROMO_ID)) AS CPC_PROMO_ID
    FROM AZCWH_PROMO_P_27986.SDW_CWH_PROMO_VIEWS
             .CH3395_V_PROMO_AVT PRM
    JOIN AZCWH_PROMO_P_27986.SDW_CWH_PROMO_VIEWS
             .CH3395_V_PROMO_BOGO_CRDT_RULE_AVT BCR
      ON PRM.PROMO_ID = BCR.PROMO_ID
    WHERE PRM.PROMO_TRADE_REQ_IND = 'Y'
      AND PRM.PROMO_SUB_TYPE_CD = 'T'
      AND BCR.CPC_PROMO_ID IS NOT NULL
),
 
current_fan AS (
    SELECT *
    FROM AZECDWP.SDW_ECDW_SRC_ATT_VIEWS.ABS_FAN_HIER_DIM
),
 
small_business_fan AS (
    SELECT DISTINCT FAN_ID
    FROM current_fan
    WHERE FINCL_LBLTY_CD = 'CRU'
      AND RPT_ACCT_NBR IS NOT NULL
      AND FAN_NM IS NOT NULL
      AND (
            ENT_TYPE_CD = 'SBA'
         OR MBLTY_SGMNT_RLP_ALT_DESC = 'MID-MARKET SMALL'
      )
),
 
promo_trans_latest AS (
    SELECT T.*
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.PROMO_TRANS T
    WHERE T.LOAD_DT_TM >=
              '2026-09-04 00:00:00'::TIMESTAMP_NTZ
      AND T.LOAD_DT_TM <
              '2026-09-05 00:00:00'::TIMESTAMP_NTZ
 
      AND T.PROMO_ID IS NOT NULL
      AND NULLIF(TRIM(T.PROMO_ID), '') IS NOT NULL
      AND LOWER(TRIM(T.PROMO_ID)) <> 'null'
 
      AND T.ADJ_CNT_NBR IS NOT NULL
      AND T.BL_CYC_CNT_NBR IS NOT NULL
      AND T.BL_CYC_CNT_NBR > 0
 
      /* Final/completed promotion transaction */
      AND T.ADJ_CNT_NBR = T.BL_CYC_CNT_NBR
      AND UPPER(TRIM(T.PROMO_STS_CD)) = 'F'
      AND T.CRDT_START_SEQ_NBR = 1
 
      AND COALESCE(
              UPPER(TRIM(T.DEL_IND)),
              'N'
          ) <> 'Y'
 
      /* Trade-in promotions only */
      AND EXISTS (
          SELECT 1
          FROM trade_in_promos P
          WHERE P.CPC_PROMO_ID =
                UPPER(TRIM(T.PROMO_ID))
      )
 
    /* Remove duplicate versions of the same transaction */
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY
            T.SRV_ACCS_ID,
            UPPER(TRIM(T.PROMO_ID)),
            T.PROMO_SEQ_NBR
        ORDER BY
            T.UPDT_DT_TM DESC,
            T.LOAD_DT_TM DESC,
            T.TRANS_TSTZ DESC
    ) = 1
),
 
completed_promos AS (
    SELECT
        T.*,
        T.BL_CYC_CNT_NBR - T.ADJ_CNT_NBR
            AS APPLICATIONS_REMAINING
    FROM promo_trans_latest T
),
 
current_subscription AS (
    SELECT *
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.SUBSRPTN_WIRLS_CURR
    WHERE BILL_SYS_GEO_ID = 2
),
 
curr_account AS (
    SELECT *
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.ACCT
    WHERE BILL_SYS_GEO_ID = 2
),
 
current_bill_cycle AS (
    SELECT *
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.BL_CYC_AVT
),
 
current_bill_statement AS (
    SELECT
        ACCT_ID,
        BILL_SYS_GEO_ID,
        BL_CYC_DT,
        TOT_BAL_DUE_AMT
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.BL_STMNT
    WHERE CURR_BLNG_IND = 'Y'
),
 
customer_graph AS (
    SELECT DISTINCT
        BAN,
        EMAIL_ADDRESS,
        FIRST_NAME,
        PHONE_NBR,
        PROFILE_SLID,
        FIRSTNET_INDICATOR
    FROM AZEDMP.SDW_EDM_DB.CUSTOMERGRAPH_ACCOUNTS
    WHERE ACCOUNT_TYPE = 'WIRELESS'
),
 
customer_graph_by_ban AS (
    SELECT
        BAN,
        MAX(EMAIL_ADDRESS)      AS CG_EMAIL,
        MAX(FIRST_NAME)         AS CG_FIRST_NM,
        MAX(PHONE_NBR)          AS CG_PHONE_NBR,
        MAX(PROFILE_SLID)       AS CG_PROFILE_SLID,
        MAX(FIRSTNET_INDICATOR) AS CG_FN_IND
    FROM customer_graph
    GROUP BY BAN
),
 
final_detail AS (
    SELECT
        /* Account and subscriber */
        A.ACCT_NBR                AS BAN,
        S.ACCT_ID,
        T.SRV_ACCS_ID,
        T.SRV_ACCS_NBR            AS PHONE_NUMBER,
        S.CURR_FAN_ID,
        S.BILL_SYS_GEO_ID,
 
        /* Promotion transaction */
        T.PROMO_ID,
        T.PROMO_SEQ_NBR,
        T.PROMO_STS_CD,
        T.PROMO_STS_RSN_CD,
        T.PROMO_STS_DT,
        T.PROMO_EFF_DT,
        T.CRDT_START_DT,
        T.CRDT_START_SEQ_NBR,
        T.NXT_CRDT_DT,
        T.PROMO_END_DT,
        T.PROMO_AMT               AS CREDIT_AMOUNT,
        T.TRANS_TYPE_CD,
        T.TRANS_SUB_TYPE_CD,
        T.TRANS_TSTZ,
 
        /* Credit progress */
        T.ADJ_CNT_NBR             AS APPLICATIONS_APPLIED,
        T.BL_CYC_CNT_NBR          AS TOTAL_APPLICATIONS,
        T.APPLICATIONS_REMAINING,
 
        /* Billing-cycle configuration */
        S.BL_CYC_ID               AS BILL_CYCLE_ID,
        C.BL_CYC_CLOS_DAY         AS BILL_CLOSE_DAY,
 
        /* Current bill */
        BS.BL_CYC_DT              AS CURRENT_BILL_CYCLE_DATE,
        TO_CHAR(
            BS.BL_CYC_DT,
            'Mon YYYY'
        )                         AS CURRENT_BILL_MONTH_YEAR,
        BS.TOT_BAL_DUE_AMT        AS CURRENT_TOTAL_BALANCE_DUE,
 
        /* Audit */
        T.UPDT_DT_TM              AS PROMO_UPDATE_DATE,
        T.LOAD_DT_TM              AS PROMO_LOAD_DATE
 
    FROM completed_promos T
 
    JOIN current_subscription S
      ON T.SRV_ACCS_ID = S.SRV_ACCS_ID
     AND T.ACCT_ID = S.ACCT_ID
 
    JOIN curr_account A
      ON S.ACCT_ID = A.ACCT_ID
     AND S.BILL_SYS_GEO_ID = A.BILL_SYS_GEO_ID
 
    JOIN current_bill_cycle C
      ON S.BL_CYC_ID = C.BL_CYC_ID
     AND A.BILL_MKT_GEO_ID = C.BILL_MKT_GEO_ID
 
    JOIN current_bill_statement BS
      ON A.ACCT_ID = BS.ACCT_ID
     AND A.BILL_SYS_GEO_ID = BS.BILL_SYS_GEO_ID
 
    WHERE EXISTS (
        SELECT 1
        FROM small_business_fan SB
        WHERE SB.FAN_ID =
              TRY_TO_NUMBER(
                  NULLIF(TRIM(S.CURR_FAN_ID), '')
              )
    )
),
 
promo_payload AS (
    SELECT
        BAN,
        MAX(ACCT_ID)                   AS ACCT_ID,
        MAX(CURR_FAN_ID)               AS CURR_FAN_ID,
        MAX(BILL_SYS_GEO_ID)           AS BILL_SYS_GEO_ID,
 
        COUNT(*)                       AS COMPLETED_PROMO_COUNT,
 
        MAX(BILL_CYCLE_ID)             AS BILL_CYCLE_ID,
        MAX(BILL_CLOSE_DAY)            AS BILL_CLOSE_DAY,
 
        MAX(CURRENT_BILL_CYCLE_DATE)   AS CURRENT_BILL_CYCLE_DATE,
        MAX(CURRENT_BILL_MONTH_YEAR)   AS CURRENT_BILL_MONTH_YEAR,
        MAX(CURRENT_TOTAL_BALANCE_DUE) AS CURRENT_TOTAL_BALANCE_DUE,
 
        ARRAY_AGG(
            OBJECT_CONSTRUCT(
                'PROMO_ID', PROMO_ID,
                'PROMO_SEQ_NBR', PROMO_SEQ_NBR,
                'PHONE_NUMBER', PHONE_NUMBER,
                'SRV_ACCS_ID', SRV_ACCS_ID,
                'PROMO_STS_CD', PROMO_STS_CD,
                'PROMO_STS_RSN_CD', PROMO_STS_RSN_CD,
                'PROMO_STS_DT', PROMO_STS_DT,
                'PROMO_EFF_DT', PROMO_EFF_DT,
                'CRDT_START_DT', CRDT_START_DT,
                'CRDT_START_SEQ_NBR', CRDT_START_SEQ_NBR,
                'NXT_CRDT_DT', NXT_CRDT_DT,
                'PROMO_END_DT', PROMO_END_DT,
                'CREDIT_AMOUNT', CREDIT_AMOUNT,
                'APPLICATIONS_APPLIED', APPLICATIONS_APPLIED,
                'TOTAL_APPLICATIONS', TOTAL_APPLICATIONS,
                'APPLICATIONS_REMAINING',
                    APPLICATIONS_REMAINING,
                'TRANS_TYPE_CD', TRANS_TYPE_CD,
                'TRANS_SUB_TYPE_CD', TRANS_SUB_TYPE_CD,
                'TRANS_TSTZ', TRANS_TSTZ,
                'PROMO_UPDATE_DATE', PROMO_UPDATE_DATE,
                'PROMO_LOAD_DATE', PROMO_LOAD_DATE
            )
        ) WITHIN GROUP (
            ORDER BY
                PHONE_NUMBER,
                PROMO_ID,
                PROMO_SEQ_NBR
        ) AS PROMO_DETAILS
 
    FROM final_detail
    GROUP BY BAN
)
 
SELECT
    P.BAN,
    P.ACCT_ID,
    P.CURR_FAN_ID,
    P.BILL_SYS_GEO_ID,
    P.COMPLETED_PROMO_COUNT,
 
    P.BILL_CYCLE_ID,
    P.BILL_CLOSE_DAY,
 
    P.CURRENT_BILL_CYCLE_DATE,
    P.CURRENT_BILL_MONTH_YEAR,
    P.CURRENT_TOTAL_BALANCE_DUE,
 
    CG.CG_EMAIL,
    CG.CG_FIRST_NM,
    CG.CG_PHONE_NBR,
    CG.CG_PROFILE_SLID,
    CG.CG_FN_IND,
 
    P.PROMO_DETAILS
 
FROM promo_payload P
 
LEFT JOIN customer_graph_by_ban CG
  ON TRIM(CG.BAN) = TRIM(P.BAN)
 
ORDER BY P.BAN;
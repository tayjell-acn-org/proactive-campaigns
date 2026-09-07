WITH trade_in_promos AS (
    SELECT DISTINCT
        UPPER(TRIM(BCR.CPC_PROMO_ID)) AS CPC_PROMO_ID
    FROM AZCWH_PROMO_P_27986.SDW_CWH_PROMO_VIEWS.CH3395_V_PROMO_AVT PRM
    JOIN AZCWH_PROMO_P_27986.SDW_CWH_PROMO_VIEWS.CH3395_V_PROMO_BOGO_CRDT_RULE_AVT BCR
      ON PRM.PROMO_ID = BCR.PROMO_ID
    WHERE PRM.PROMO_TRADE_REQ_IND = 'Y'
      AND PRM.PROMO_SUB_TYPE_CD = 'T'
      AND BCR.CPC_PROMO_ID IS NOT NULL
),
 
current_fan AS (
    SELECT *
    FROM AZECDWP.SDW_ECDW_SRC_ATT_VIEWS.ABS_FAN_HIER_DIM
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY FAN_ID
        ORDER BY
            LOAD_DT_TM DESC,
            UPDT_DT_TM DESC
    ) = 1
),
 
small_business_fan AS (
    SELECT DISTINCT
        FAN_ID
    FROM current_fan
    WHERE FINCL_LBLTY_CD = 'CRU'
      AND RPT_ACCT_NBR IS NOT NULL
      AND FAN_NM IS NOT NULL
      AND (
            ENT_TYPE_CD = 'SBA'
         OR MBLTY_SGMNT_RLP_ALT_DESC = 'MID-MARKET SMALL'
      )
),
 
promo_hist_latest AS (
    SELECT
        H.*
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.PROMO_HIST H
    WHERE H.UPDT_DT_TM >=
              '2026-08-28 00:00:00'::TIMESTAMP_NTZ
      AND H.UPDT_DT_TM <
              '2026-08-29 00:00:00'::TIMESTAMP_NTZ
 
      AND H.PROMO_ID IS NOT NULL
      AND NULLIF(TRIM(H.PROMO_ID), '') IS NOT NULL
      AND LOWER(TRIM(H.PROMO_ID)) <> 'null'
 
      AND H.ADJ_CNT_NBR IS NOT NULL
      AND H.BL_CYC_CNT_NBR IS NOT NULL
      AND H.BL_CYC_CNT_NBR > 0
 
      AND UPPER(TRIM(H.PROMO_STS_CD)) = 'F'
      AND COALESCE(
              UPPER(TRIM(H.DEL_IND)),
              'N'
          ) <> 'Y'
 
      /* Trade-in promotions only */
      AND EXISTS (
          SELECT 1
          FROM trade_in_promos T
          WHERE T.CPC_PROMO_ID =
                UPPER(TRIM(H.PROMO_ID))
      )
 
    QUALIFY ROW_NUMBER() OVER (
        PARTITION BY
            H.SRV_ACCS_ID,
            UPPER(TRIM(H.PROMO_ID)),
            H.PROMO_SEQ_NBR
        ORDER BY
            H.UPDT_DT_TM DESC,
            H.LOAD_DT_TM DESC
    ) = 1
),
 
expiring_promos AS (
    SELECT
        H.*,
        H.BL_CYC_CNT_NBR - H.ADJ_CNT_NBR
            AS APPLICATIONS_REMAINING
    FROM promo_hist_latest H
 
    /* One final promotional credit remains */
    WHERE H.ADJ_CNT_NBR = H.BL_CYC_CNT_NBR
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
 
/*
Aggregate Customer Graph separately so multiple Customer Graph rows
do not duplicate promotions in PROMO_DETAILS.
*/
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
        A.ACCT_NBR                    AS BAN,
        S.ACCT_ID,
        H.SRV_ACCS_ID,
        H.SRV_ACCS_NBR                AS PHONE_NUMBER,
        S.CURR_FAN_ID,
        S.BILL_SYS_GEO_ID,
 
        /* Promotion */
        H.PROMO_ID,
        H.PROMO_SEQ_NBR,
        H.PROMO_STS_CD,
        H.PROMO_STS_RSN_CD,
        H.PROMO_STS_DT,
        H.PROMO_EFF_DT,
        H.CRDT_START_DT,
        H.NXT_CRDT_DT                 AS EXPECTED_FINAL_CREDIT_DATE,
        H.PROMO_END_DT,
        H.PROMO_AMT                   AS CREDIT_AMOUNT,
 
        /* Credit progress */
        H.ADJ_CNT_NBR                 AS APPLICATIONS_APPLIED,
        H.BL_CYC_CNT_NBR              AS TOTAL_APPLICATIONS,
        H.APPLICATIONS_REMAINING,
 
        /* Billing cycle configuration */
        S.BL_CYC_ID                   AS BILL_CYCLE_ID,
        C.BL_CYC_CLOS_DAY             AS BILL_CLOSE_DAY,
 
        /* Current bill */
        BS.BL_CYC_DT                  AS CURRENT_BILL_CYCLE_DATE,
        TO_CHAR(
            BS.BL_CYC_DT,
            'Mon YYYY'
        )                             AS CURRENT_BILL_MONTH_YEAR,
        BS.TOT_BAL_DUE_AMT            AS CURRENT_TOTAL_BALANCE_DUE,
 
        /* Audit */
        H.UPDT_DT_TM                  AS PROMO_UPDATE_DATE,
        H.LOAD_DT_TM                  AS PROMO_LOAD_DATE
 
    FROM expiring_promos H
 
    JOIN current_subscription S
      ON H.SRV_ACCS_ID = S.SRV_ACCS_ID
     AND H.ACCT_ID = S.ACCT_ID
 
    JOIN curr_account A
      ON S.ACCT_ID = A.ACCT_ID
     AND S.BILL_SYS_GEO_ID = A.BILL_SYS_GEO_ID
 
    JOIN current_bill_cycle C
      ON S.BL_CYC_ID = C.BL_CYC_ID
     AND A.BILL_MKT_GEO_ID = C.BILL_MKT_GEO_ID
 
    JOIN current_bill_statement BS
      ON A.ACCT_ID = BS.ACCT_ID
 
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
        /* BAN-level attributes */
        BAN,
        MAX(ACCT_ID)                      AS ACCT_ID,
        MAX(CURR_FAN_ID)                  AS CURR_FAN_ID,
        MAX(BILL_SYS_GEO_ID)              AS BILL_SYS_GEO_ID,
 
        COUNT(*)                          AS CURRENT_PROMO_COUNT,
 
        MAX(BILL_CYCLE_ID)                AS BILL_CYCLE_ID,
        MAX(BILL_CLOSE_DAY)               AS BILL_CLOSE_DAY,
 
        MAX(CURRENT_BILL_CYCLE_DATE)      AS CURRENT_BILL_CYCLE_DATE,
        MAX(CURRENT_BILL_MONTH_YEAR)      AS CURRENT_BILL_MONTH_YEAR,
        MAX(CURRENT_TOTAL_BALANCE_DUE)    AS CURRENT_TOTAL_BALANCE_DUE,
 
        /* Promotion and line-level attributes */
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
                'EXPECTED_FINAL_CREDIT_DATE',
                    EXPECTED_FINAL_CREDIT_DATE,
                'PROMO_END_DT', PROMO_END_DT,
                'CREDIT_AMOUNT', CREDIT_AMOUNT,
                'APPLICATIONS_APPLIED', APPLICATIONS_APPLIED,
                'TOTAL_APPLICATIONS', TOTAL_APPLICATIONS,
                'APPLICATIONS_REMAINING',
                    APPLICATIONS_REMAINING,
                'PROMO_UPDATE_DATE', PROMO_UPDATE_DATE,
                'PROMO_LOAD_DATE', PROMO_LOAD_DATE
            )
        ) WITHIN GROUP (
            ORDER BY
                EXPECTED_FINAL_CREDIT_DATE,
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
    P.CURRENT_PROMO_COUNT,
 
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
  ON CG.BAN = P.BAN;
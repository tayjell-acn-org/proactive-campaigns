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
 
pending_latest AS (
    SELECT
        P.SRV_ACCS_ID,
        P.BILL_SYS_GEO_ID,
        P.ACTVT_SEQ_NBR,
        P.ACTVT_AMT,
        P.ACTVT_EFF_DT,
        P.ACTVT_ADD_DT,
        P.LOAD_DT_TM,
        P.UPDT_DT_TM,
        P.PROMO_ID,
        P.PROMO_CURR_CRDT_CNT_NBR
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.SUBSRPTN_PNDG_ACTVT P
    WHERE P.BILL_SYS_GEO_ID = 2
      AND P.PROMO_ID IS NOT NULL
      AND LOWER(TRIM(P.PROMO_ID)) <> 'null'
      AND P.ACTVT_ADD_DT = DATE '2026-09-02'
      AND P.PROMO_CURR_CRDT_CNT_NBR = 1
 
      AND EXISTS (
          SELECT 1
          FROM trade_in_promos T
          WHERE T.CPC_PROMO_ID =
                UPPER(TRIM(P.PROMO_ID))
      )
 
),
 
/*
Exclude a line/promotion combination if it has ever had
a valid expired status in PROMO_HIST.
*/
clean_pending AS (
    SELECT
        P.*
    FROM pending_latest P
    WHERE NOT EXISTS (
        SELECT 1
        FROM AZECDWP.SDW_ECDW_ATT_VIEWS.PROMO_HIST H
        WHERE H.SRV_ACCS_ID = P.SRV_ACCS_ID
          AND UPPER(TRIM(H.PROMO_ID)) =
              UPPER(TRIM(P.PROMO_ID))
          AND UPPER(TRIM(H.PROMO_STS_CD)) = 'E'
          AND COALESCE(
                  UPPER(TRIM(H.DEL_IND)),
                  'N'
              ) <> 'Y'
    )
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
 
customer_graph AS (
    SELECT
        BAN,
        EMAIL_ADDRESS,
        FIRST_NAME,
        PHONE_NBR,
        PROFILE_SLID,
        FIRSTNET_INDICATOR
    FROM AZEDMP.SDW_EDM_DB.CUSTOMERGRAPH_ACCOUNTS
    WHERE ACCOUNT_TYPE = 'WIRELESS'
),
 
platform_handler AS (
    SELECT
        FAN_ID,
        PLTFM_HNDLR
    FROM AZECDWP.SDW_ECDW_ATT_VIEWS.FAN_PLTFM_HNDLR_SNPSHT
),
 
final_detail AS (
    SELECT
        A.ACCT_NBR                AS BAN,
        S.ACCT_ID,
        P.SRV_ACCS_ID,
        S.CURR_SRV_ACCS_NBR       AS PHONE_NUMBER,
        S.CURR_FAN_ID,
        PH.PLTFM_HNDLR            AS PLATFORM_HANDLER,
        P.PROMO_ID,
        P.PROMO_CURR_CRDT_CNT_NBR AS CURRENT_CREDIT_COUNT,
        P.ACTVT_AMT               AS CREDIT_AMOUNT,
        P.ACTVT_EFF_DT            AS EFFECTIVE_DATE,
        P.ACTVT_ADD_DT            AS ADDED_DATE,
        P.LOAD_DT_TM              AS LOAD_DATE,
        P.UPDT_DT_TM              AS UPDATE_DATE,
        S.BL_CYC_ID               AS BILL_CYCLE_ID,
        C.BL_CYC_CLOS_DAY         AS BILL_CLOSE_DAY,
 
        CG.EMAIL_ADDRESS          AS CG_EMAIL,
        CG.FIRST_NAME             AS CG_FIRST_NM,
        CG.PHONE_NBR              AS CG_PHONE_NBR,
        CG.PROFILE_SLID           AS CG_PROFILE_SLID,
        CG.FIRSTNET_INDICATOR     AS CG_FN_IND
 
    FROM clean_pending P
 
    JOIN current_subscription S
      ON P.SRV_ACCS_ID = S.SRV_ACCS_ID
     AND P.BILL_SYS_GEO_ID = S.BILL_SYS_GEO_ID
 
    JOIN curr_account A
      ON S.ACCT_ID = A.ACCT_ID
     AND S.BILL_SYS_GEO_ID = A.BILL_SYS_GEO_ID
 
    JOIN current_bill_cycle C
      ON S.BL_CYC_ID = C.BL_CYC_ID
     AND A.BILL_MKT_GEO_ID = C.BILL_MKT_GEO_ID
 
    LEFT JOIN customer_graph CG
      ON TRIM(CG.BAN) = TRIM(A.ACCT_NBR)
 
    LEFT JOIN platform_handler PH
      ON TRY_TO_NUMBER(PH.FAN_ID) =
         TRY_TO_NUMBER(S.CURR_FAN_ID)
 
    WHERE EXISTS (
        SELECT 1
        FROM small_business_fan SB
        WHERE SB.FAN_ID =
              TRY_TO_NUMBER(S.CURR_FAN_ID)
    )
)
 
SELECT
    BAN,
    MAX(ACCT_ID)              AS ACCT_ID,
    MAX(CURR_FAN_ID)          AS CURR_FAN_ID,
    MAX(PLATFORM_HANDLER)     AS PLATFORM_HANDLER,
 
    COUNT(*)                  AS CURRENT_CREDIT_COUNT,
 
    MAX(BILL_CYCLE_ID)        AS BILL_CYCLE_ID,
    MAX(BILL_CLOSE_DAY)       AS BILL_CLOSE_DAY,
 
    MAX(CG_EMAIL)             AS CG_EMAIL,
    MAX(CG_FIRST_NM)          AS CG_FIRST_NM,
    MAX(CG_PHONE_NBR)         AS CG_PHONE_NBR,
    MAX(CG_PROFILE_SLID)      AS CG_PROFILE_SLID,
    MAX(CG_FN_IND)            AS CG_FN_IND,
 
    ARRAY_AGG(
        OBJECT_CONSTRUCT(
            'PROMO_ID',       PROMO_ID,
            'PHONE_NUMBER',   PHONE_NUMBER,
            'SRV_ACCS_ID',    SRV_ACCS_ID,
            'CREDIT_AMOUNT',  CREDIT_AMOUNT,
            'EFFECTIVE_DATE', EFFECTIVE_DATE,
            'ADDED_DATE',     ADDED_DATE
        )
    ) AS CREDIT_DETAILS
 
FROM final_detail
GROUP BY BAN
ORDER BY BAN;
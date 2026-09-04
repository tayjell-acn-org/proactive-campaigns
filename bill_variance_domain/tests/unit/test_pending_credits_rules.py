from campaigns.pending_credits import rules

def test_build_credit_list():
   source_context = {
       "CREDIT_DETAILS": [
           {
               "PHONE_NUMBER": "4045552718",
               "CREDIT_AMOUNT": -25,
           }
       ]
   }
   credit_list = rules._build_credit_list(source_context)
   assert len(credit_list) == 1
   assert credit_list[0]["sequence"] == 1
   assert credit_list[0]["creditType"] == "Trade In"
   assert credit_list[0]["creditName"] == "Trade In"
   assert credit_list[0]["creditAmount"] == -25.0
   assert credit_list[0]["lineLast4"] == "2718"

def test_build_credit_list_limits_to_three():
   source_context = {
       "CREDIT_DETAILS": [
           {"PHONE_NUMBER": "4045551111", "CREDIT_AMOUNT": -25},
           {"PHONE_NUMBER": "4045552222", "CREDIT_AMOUNT": -10},
           {"PHONE_NUMBER": "4045553333", "CREDIT_AMOUNT": -5},
           {"PHONE_NUMBER": "4045554444", "CREDIT_AMOUNT": -15},
       ]
   }
   credit_list = rules._build_credit_list(source_context)
   assert len(credit_list) == 3
   assert credit_list[0]["lineLast4"] == "1111"
   assert credit_list[1]["lineLast4"] == "2222"
   assert credit_list[2]["lineLast4"] == "3333"

def test_get_customer_contact_info_with_email_and_phone():
   source_context = {
       "CG_FIRST_NM": "SARAH",
       "CG_EMAIL": "sarah.jenkins@yahoo.com",
       "CG_PHONE_NBR": "4045552718",
       "CG_PROFILE_SLID": "",
   }
   contact = rules._get_customer_contact_info(source_context)
   assert contact["first_name"] == "SARAH"
   assert contact["email"] == "sarah.jenkins@yahoo.com"
   assert contact["phone"] == "4045552718"
   assert contact["online_registered"] is False

def test_get_customer_contact_info_email_only():
   source_context = {
       "CG_FIRST_NM": "SARAH",
       "CG_EMAIL": "sarah.jenkins@yahoo.com",
       "CG_PHONE_NBR": "",
       "CG_PROFILE_SLID": "",
   }
   contact = rules._get_customer_contact_info(source_context)
   assert contact["first_name"] == "SARAH"
   assert contact["email"] == "sarah.jenkins@yahoo.com"
   assert "phone" not in contact
   assert contact["online_registered"] is False

def test_get_customer_contact_info_sms_only():
   source_context = {
       "CG_FIRST_NM": "SARAH",
       "CG_EMAIL": "",
       "CG_PHONE_NBR": "4045552718",
       "CG_PROFILE_SLID": "",
   }
   contact = rules._get_customer_contact_info(source_context)
   assert contact["first_name"] == "SARAH"
   assert contact["phone"] == "4045552718"
   assert "email" not in contact
   assert contact["online_registered"] is False

def test_get_customer_contact_info_no_contact():
   source_context = {
       "CG_FIRST_NM": "SARAH",
       "CG_EMAIL": "",
       "CG_PHONE_NBR": "",
       "CG_PROFILE_SLID": "",
   }
   contact = rules._get_customer_contact_info(source_context)
   assert contact["first_name"] == "SARAH"
   assert "email" not in contact
   assert "phone" not in contact
   assert contact["online_registered"] is False

def test_get_customer_contact_info_uses_profile_slid_when_registered():
   source_context = {
       "CG_FIRST_NM": "SARAH",
       "CG_EMAIL": "billing@example.com",
       "CG_PHONE_NBR": "4045552718",
       "CG_PROFILE_SLID": "online@example.com",
   }
   contact = rules._get_customer_contact_info(source_context)
   assert contact["email"] == "online@example.com"
   assert contact["online_registered"] is True

def test_get_acct_info():
   source_context = {
       "BAN": "298541763218",
       "CURR_FAN_ID": "71234567",
       "PLATFORM_HANDLER": "MyATT",
   }
   acct_info = rules._get_acct_info(source_context)
   assert acct_info["ban"] == "298541763218"
   assert acct_info["fan"] == "71234567"
   assert acct_info["platform_handler"] == "MyATT"
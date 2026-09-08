from campaigns.promotion_expiry import rules

def test_build_promo_list():
   source_context = {
       "PROMO_DETAILS": [
           {
               "PHONE_NUMBER": "4045552718",
               "CREDIT_AMOUNT": -25,
           }
       ]
   }
   promo_list = rules._build_promo_list(source_context)
   assert len(promo_list) == 1
   assert promo_list[0]["sequence"] == 1
   assert promo_list[0]["promoType"] == "Trade-In"
   assert promo_list[0]["promoAmount"] == -25.0
   assert promo_list[0]["lineLast4"] == "2718"

def test_build_promo_list_limits_to_three():
   source_context = {
       "PROMO_DETAILS": [
           {"PHONE_NUMBER": "4045551111", "CREDIT_AMOUNT": -25},
           {"PHONE_NUMBER": "4045552222", "CREDIT_AMOUNT": -10},
           {"PHONE_NUMBER": "4045553333", "CREDIT_AMOUNT": -5},
           {"PHONE_NUMBER": "4045554444", "CREDIT_AMOUNT": -15},
       ]
   }
   promo_list = rules._build_promo_list(source_context)
   assert len(promo_list) == 3
   assert promo_list[0]["lineLast4"] == "1111"
   assert promo_list[1]["lineLast4"] == "2222"
   assert promo_list[2]["lineLast4"] == "3333"

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

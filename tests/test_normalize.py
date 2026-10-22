from leadcrm.normalize import company_key, norm_email, norm_name, norm_phone, norm_size, normalize


def test_phone_local_to_international():
    assert norm_phone("0812-7000-1001") == "6281270001001"
    assert norm_phone("+62 813-7000-1004") == "6281370001004"
    assert norm_phone("0049 160 5550 2002") == "4916055502002"
    assert norm_phone("123") == ""


def test_email_and_name():
    assert norm_email(" Maya.Santosa@Kencanaretail.TEST ") == "maya.santosa@kencanaretail.test"
    assert norm_email("no email here") == ""
    assert norm_name("maya   SANTOSA") == "Maya Santosa"


def test_company_key_strips_legal_suffix():
    assert company_key("PT Kencana Retail") == company_key("Kencana Retail Tbk") == "kencana retail"
    assert company_key("Yamada Hotels Co.") == "yamada hotels"


def test_size_buckets():
    assert norm_size("11-50") == "11-50"
    assert norm_size("about 120 employees") == "51-200"
    assert norm_size("") == ""


def test_whatsapp_pulls_company_and_email():
    l = normalize({"from": "081270001017", "profile_name": "bayu", "text": "Halo, saya dari Toko Bayu Elektronik. a@b.test"},
                  "whatsapp")
    assert l["phone"] == "6281270001017" and l["company"].startswith("Toko Bayu") and l["email"] == "a@b.test"
    assert l["source"] == "whatsapp"

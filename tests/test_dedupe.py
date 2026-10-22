from leadcrm.dedupe import find_duplicate
from leadcrm.evaluate import dedupe_eval

A = {"name": "Hiro Yamada", "email": "hiro@yamadahotels.test", "phone": "", "company": "Yamada Hotels", "id": 1}


def test_email_phone_fuzzy():
    assert find_duplicate({"email": "hiro@yamadahotels.test"}, [A])[1] == "same email"
    assert find_duplicate({"phone": "62811", "email": ""}, [{**A, "phone": "62811"}])[1] == "same phone"
    d, why = find_duplicate({"name": "Hiro Yamada", "email": "h@other.test", "company": "Yamada Hotels Co."}, [A])
    assert d is A and why.startswith("similar name")


def test_different_person_same_company_is_not_duplicate():
    assert find_duplicate({"name": "Kenji Sato", "email": "k@x.test", "company": "Yamada Hotels"}, [A])[0] is None


def test_planted_duplicates_all_caught_no_false_alarms():
    r = dedupe_eval()
    assert r["caught"] == r["planted"] == 4 and r["false_positives_demo"] == 0 and r["false_alarms"] == 0

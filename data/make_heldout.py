"""Hand-written held-out leads (labels = my own judgement of how a sales lead should treat them).
Written once, before the rule weights were tuned on the generated dev set; never used for tuning."""
import json, pathlib
F = ("source", "name", "email", "phone", "company", "role", "company_size", "budget", "timeline", "message", "label")
ROWS = [
 ("web_form","Rina Halim","rina@tokobaru.test","081234500001","Toko Baru Retail","Operations Director","51-200","USD 15,000","Next 2 weeks","We need our order emails routed into a CRM automatically. Can we get a proposal and a demo?","hot"),
 ("web_form","Marcus Feld","m.feld@feldlogistics.test","+49 151 0000 1102","Feld Logistics GmbH","Head of Customer Ops","201-1000","€20k","This month","Looking to automate inbound quote requests, ~300/day. Want to start a pilot ASAP.","hot"),
 ("web_form","Dewi Saraswati","dewi.s@gmail.com","","","","","","","hi, just curious what you do","cold"),
 ("web_form","Arjun Mehta","arjun@brightpath.test","","BrightPath Clinics","Practice Manager","11-50","","Next quarter","We get appointment requests from WhatsApp and a web form. Interested in automating triage.","warm"),
 ("web_form","Linda Ko","linda.ko@kocatering.test","","Ko Catering","Owner","1-10","$1,500","1-2 months","Want a simple workflow so catering orders land in a spreadsheet and I get a Telegram ping.","warm"),
 ("web_form","SEO Pro Team","sales@rankfast.test","","RankFast","","","","","We offer SEO services and quality backlinks to rank on Google page one. Reply for pricing.","cold"),
 ("web_form","Budi Santoso","budi.s@yahoo.com","","","Student","","","","Hi, I'm a student doing a university project on n8n, can you help?","cold"),
 ("web_form","Hannah Ortiz","hannah@ortizlegal.test","","Ortiz Legal","Managing Partner","11-50","USD 8,000","Within a month","Our intake form emails go to one inbox and we lose leads. Need CRM integration and a quote.","hot"),
 ("web_form","Tomasz Nowak","tnowak@nowakparts.test","","Nowak Parts","Purchasing Manager","51-200","","Not sure when","Researching automation tools for next year budget planning.","cold"),
 ("web_form","Siti Aminah","siti@griyaspa.test","0813 7777 0010","Griya Spa","Pemilik","11-50","Rp 40 juta","Bulan ini","Mau otomatisasi booking dari WhatsApp ke spreadsheet, minta penawaran harga.","hot"),
 ("web_form","Kevin Tan","kevin.tan@outlook.com","","","","","","Next month","Can you build me a CRM automation?","warm"),
 ("web_form","Priya Raman","priya@luminaedu.test","","Lumina Education","Marketing Lead","51-200","","1-3 months","We run webinars and want sign-ups scored and pushed to our CRM. What does pricing look like?","warm"),
 ("web_form","Jake Miller","jake@millerhvac.test","","Miller HVAC","Owner","11-50","$12k","ASAP","Missed calls and web leads are killing us. Need lead routing to techs and a CRM, this week if possible.","hot"),
 ("web_form","Aiko Sato","aiko.sato@icloud.com","","","Fresh graduate","","","","Looking for a job in automation, attaching my CV. Are you hiring?","cold"),
 ("web_form","Omar Haddad","omar@haddadrealty.test","","Haddad Realty","Sales Manager","11-50","","","Interested in automating property enquiry follow-ups.","warm"),
 ("web_form","Grace Liu","grace@petalflorist.test","","Petal Florist","Owner","1-10","$300","No rush","Maybe later this year I want online orders in a sheet.","cold"),
 ("web_form","Daniel Brooks","dbrooks@summitfin.test","","Summit Financial Advisors","COO","51-200","USD 25,000","Q1","We want to integrate our website forms, calendar and CRM, and score leads before advisors call.","warm"),
 ("web_form","Fajar Nugroho","fajar@kopikita.test","0857 1111 2222","Kopi Kita","Head of Operations","51-200","Rp 120 juta","2 weeks","Need implementation of lead intake from 3 forms + WhatsApp into our CRM before our franchise launch.","hot"),
 ("web_form","Emily Clark","emily@clarkdesign.test","","Clark Design Studio","Designer","1-10","","","Do you do website design?","cold"),
 ("web_form","Victor Huang","victor@huangmfg.test","","Huang Manufacturing","IT Manager","201-1000","","This quarter","Evaluating n8n vs Zapier for distributor enquiries. Could you do a demo?","warm"),
 ("web_form","Nadia Putri","nadia@rumahsehat.test","","Rumah Sehat Clinic","Admin","11-50","","","Can you send me a brochure?","cold"),
 ("web_form","Oliver Grant","oliver@grantgyms.test","","Grant Gyms","Founder","51-200","$6,000","Next week","Membership enquiries from Instagram and web need to hit our CRM with a score. Ready to sign if the quote works.","hot"),
 ("web_form","Mei Wong","mei@wongtrading.test","","Wong Trading","Director","11-50","","Next year","Just exploring options for now.","cold"),
 ("web_form","Rizky Pratama","rizky.p@gmail.com","0812 3456 7890","","Freelancer","","Rp 3 juta","Bulan depan","Mau bikin automasi CRM kecil buat klien saya.","warm"),
 ("web_form","Sara Lindqvist","sara@nordichomes.test","","Nordic Homes","VP Sales","201-1000","EUR 30,000","Immediately","Our sales team needs scored, de-duplicated leads in HubSpot. Want a proposal and contract this month.","hot"),
 ("web_form","Ahmad Fauzi","ahmad@fauzimotor.test","","Fauzi Motor","Owner","11-50","","","What is the price for an automation like this?","warm"),
 ("web_form","Chloe Martin","chloe@martinbakery.test","","Martin Bakery","Manager","1-10","","","hello","cold"),
 ("web_form","Hiroshi Kato","h.kato@katoparts.test","","Kato Parts","Sales Lead","51-200","$4,000","3 months","Interested in automating RFQ intake to our CRM.","warm"),
 ("web_form","Laura Bianchi","laura@bianchievents.test","","Bianchi Events","Event Director","11-50","$9,500","Before the end of the month","Wedding enquiries pile up in email. Need a CRM pipeline and automatic replies. Can you quote?","hot"),
 ("web_form","Crypto Gains","promo@cryptogains.test","","","","","","","Earn 300% with crypto signals, join now","cold"),
 ("whatsapp","Andi Wijaya","","6281299990001","","","","","","Halo, saya dari Toko Elektronik Jaya, mau tanya harga otomatisasi chat pelanggan ke CRM. Butuh segera minggu ini, budget sekitar 60 juta.","hot"),
 ("whatsapp","Yuni","","6281388880002","","","","","","kak ini jasa apa ya?","cold"),
 ("whatsapp","Hendra","","6285677770003","","","","","","Saya dari Bengkel Hendra, tertarik automasi booking servis. Kira2 harganya berapa?","warm"),
 ("whatsapp","Lisa M","","6287766660004","","","","","","Hi from Lisa Bakes, can you set up an order form that goes to a sheet? next month maybe","warm"),
 ("whatsapp","Rudi","","6281122220005","","","","","","Gan ada lowongan kerja? saya mau apply for admin","cold"),
 ("web_form","Fiona Reyes","fiona@reyesdental.test","","Reyes Dental Group","Operations Manager","51-200","","","We have 4 locations and want new-patient enquiries scored and routed to the nearest clinic.","warm"),
 ("web_form","George Patel","george@pateltravel.test","","Patel Travel","Owner","11-50","USD 2,500","Next month","Quote requests from our site need to go into a CRM with a follow-up reminder.","warm"),
 ("web_form","Ines Costa","ines@costaimports.test","","Costa Imports","CEO","201-1000","$40k","This month","We want a full lead-to-CRM automation with scoring and Slack alerts. Please send a proposal.","hot"),
 ("web_form","Ben Carter","ben.carter@gmail.com","","","","","","","Can I get a free template?","cold"),
 ("web_form","Yusuf Rahman","yusuf@rahmanlaw.test","","Rahman & Partners","Partner","11-50","","Within 2 weeks","Need intake automation for client enquiries, can we book a call and a demo?","hot"),
]
out = pathlib.Path(__file__).with_name("heldout.jsonl")
with out.open("w") as f:
    for r in ROWS:
        f.write(json.dumps(dict(zip(F, r)), ensure_ascii=False) + "\n")
print(len(ROWS), "rows ->", out)

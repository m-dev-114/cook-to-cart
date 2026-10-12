"""MOCKED, live-shaped Instamart catalog used ONLY by the evaluation harness and tests. Never served to users."""
import re
from engine import sing as engine_sing

RAW = """mint|Mint Leaves|1 bunch|12;mintgum|Doublemint Peppermint Flavour Chewing Gum|13 g|10;mintcandy|Impact Mints Sugar Free Mints Fresh Mints|14 g|150;corleaf|Coriander Leaves (Dhaniya Patta)|1 bunch|10;corpow|Coriander Powder|100 g|30;corseed|Coriander Seeds (Dhania)|100 g|35
curryleaf|Curry Leaves (Kadi Patta)|1 bunch|8;jeera|Cumin Seeds (Jeera)|100 g|60;jeerapow|Cumin Powder|100 g|55;haldi|Turmeric Powder (Haldi)|100 g|26;rajma|Rajma Red Kidney Beans|500 g|90;rajmamasala|Rajma Masala|50 g|40
paneer|Fresh Paneer|200 g|85;paneermix|Paneer Butter Masala Mix|50 g|45;curd|Classic Curd (Dahi)|400 g|40;curdflav|Strawberry Flavoured Yogurt|100 g|30;ghee|Cow Ghee|500 ml|300;atta|Whole Wheat Atta|1 kg|55
besan|Besan Gram Flour|500 g|60;suji|Suji Rava|500 g|35;poha|Poha Thick|500 g|40;tamarind|Tamarind (Imli)|200 g|45;tamcandy|Imli Candy|50 g|20;jaggery|Jaggery (Gur)|500 g|60
hing|Asafoetida (Hing) Powder|50 g|70;ajwain|Ajwain Carom Seeds|100 g|40;saunf|Fennel Seeds (Saunf)|100 g|35;elaichi|Green Cardamom (Elaichi)|50 g|220;clove|Cloves (Laung)|50 g|110;cinn|Cinnamon Sticks (Dalchini)|50 g|60
bay|Bay Leaf (Tej Patta)|20 g|25;blacksalt|Black Salt (Kala Namak)|100 g|25;salt|Iodised Salt|1 kg|20;amchur|Dry Mango Powder (Amchur)|100 g|45;kasuri|Kasuri Methi|25 g|30;methi|Fresh Methi Leaves|1 bunch|15
methiseed|Methi Seeds (Fenugreek)|100 g|30;mustoil|Mustard Oil (Sarson Ka Tel)|1 l|190;sunoil|Sunflower Refined Oil|1 l|140;coco|Fresh Coconut (Nariyal)|1 piece|40;cocopow|Desiccated Coconut Powder|100 g|60;lauki|Bottle Gourd (Lauki)|1 piece|35
bhindi|Ladies Finger (Bhindi)|250 g|30;brinjal|Brinjal (Baingan)|500 g|40;capsg|Green Capsicum (Shimla Mirch)|250 g|30;capsr|Red Capsicum|1 piece|50;gchilli|Green Chilli (Hari Mirch)|100 g|12;gchillisauce|Green Chilli Sauce|200 g|60
adrak|Ginger (Adrak)|100 g|15;adrakpaste|Ginger Paste|100 g|30;garlic|Garlic (Lehsun)|250 g|40;garlicpaste|Garlic Paste|100 g|22;onion|Onion (Pyaaz)|1 kg|40;tomato|Tomato (Tamatar)|500 g|25
potato|Potato (Aloo)|1 kg|35;peas|Green Peas (Matar)|500 g|60;palak|Spinach (Palak)|1 bunch|15;lemon|Lemon (Nimbu)|4 piece|20;butter|Amul Butter|100 g|58;vegan|Plant Based Butter Alternative|100 g|120
basmati|Basmati Rice|1 kg|140;brokenbas|Broken Basmati Rice|1 kg|69;chana|Kabuli Chana|500 g|75;chanadal|Chana Dal|500 g|60;toor|Toor Dal (Arhar)|500 g|90;moong|Moong Dal|500 g|80
chicken|Chicken Curry Cut|500 g|180;chickchips|Chicken Flavour Chips|50 g|20;egg|Farm Fresh Eggs|6 piece|60;sugar|Sugar|1 kg|50;milk|Toned Milk|500 ml|30;cream|Fresh Cream|200 ml|65
garammasala|Garam Masala|100 g|50;redchilli|Red Chilli Powder|100 g|40;cumsauce|Mint Chutney|200 g|50;saffron|Saffron (Kesar)|1 g|300;kaddu|Pumpkin (Kaddu)|500 g|30;arbi|Colocasia (Arbi)|500 g|40"""

CATALOG = []
for rec in re.split(r"[;\n]", RAW):
    if not rec.strip(): continue
    i, name, pack, price = rec.split("|"); q, u = pack.split()
    CATALOG.append(dict(product_id=i, name=name, brand="", variant=None, category=None, pack_quantity=float(q), pack_unit=u, pack_label=pack, price=float(price), availability=True, image_url=None, rating=None))

# The mock search engine mimics a retail search: all query words must appear in name (singular-insensitive); a few semantic redirects mimic the real engine's own synonym handling.
SEMANTIC = {"hara dhaniya": "coriander leaves", "shimla": "capsicum", "kothimbir": "coriander leaves"}


def _t(s): return {engine_sing(w) for w in re.findall(r"[a-z0-9]+", s.lower())}


def search(q, catalog=None, unavailable=()):
    q = SEMANTIC.get(q.lower().strip(), q); qt = _t(q); out = []
    for p in (catalog or CATALOG):
        if qt and qt <= _t(p["name"]): out.append(dict(p, availability=p["product_id"] not in unavailable))
    return sorted(out, key=lambda p: len(_t(p["name"])))

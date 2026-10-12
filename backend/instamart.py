import engine

_C = [
("chk-a1","Boneless Chicken Breast","Brand A","Meat",500,"g",280,1),("chk-b1","Boneless Chicken Breast","Brand B","Meat",1000,"g",480,1),
("chk-c1","Boneless Chicken Breast","Brand C","Meat",450,"g",240,1),("chk-d1","Boneless Chicken Breast","Brand D","Meat",250,"g",150,0),
("chk-e1","Bone-in Chicken Breast","Brand A","Meat",500,"g",220,1),("chk-f1","Chicken Liver","Brand A","Meat",500,"g",150,1),
("pas-c1","Penne Pasta","Brand C","Pantry",250,"g",70,1),("pas-d1","Penne Pasta","Brand D","Pantry",500,"g",120,1),
("pas-e1","Spaghetti Pasta","Brand C","Pantry",500,"g",110,1),("tom-a1","Tomato","Brand A","Produce",4,"piece",60,1),
("tom-b1","Tomato Hybrid","Brand B","Produce",500,"g",40,1),("moz-e1","Mozzarella Cheese","Brand E","Dairy",200,"g",180,1),
("moz-f1","Mozzarella Cheese","Brand F","Dairy",500,"g",390,1),("moz-g1","Mozzarella Cheese Block","Brand G","Dairy",100,"g",95,0),
("piz-h1","Pizza Cheese","Brand H","Dairy",200,"g",150,1),("oil-a1","Extra Virgin Olive Oil","Brand A","Pantry",250,"ml",160,1),
("oil-a2","Extra Virgin Olive Oil","Brand A","Pantry",500,"ml",300,1),("flr-a1","Wheat Flour","Brand A","Pantry",500,"g",50,1),
("mda-b1","Refined Flour (Maida)","Brand B","Pantry",500,"g",55,1),("mda-b2","Refined Flour (Maida)","Brand B","Pantry",1000,"g",100,1),
("flr-a2","Wheat Flour","Brand A","Pantry",1000,"g",90,1),("rice-a1","Basmati Rice","Brand A","Pantry",1000,"g",110,1),
("onn-a1","Onion","Brand A","Produce",1000,"g",45,1),("gar-a1","Garlic","Brand A","Produce",100,"g",30,1),
("egg-a1","Eggs","Brand A","Dairy",6,"piece",78,1),("egg-a2","Eggs","Brand A","Dairy",12,"piece",140,1),
("but-a1","Butter","Brand A","Dairy",100,"g",58,1),("milk-001","Milk","Brand A","Dairy",500,"ml",30,1),
("brd-001","Bread","Brand A","Bakery",400,"g",45,1),("slt-a1","Salt","Brand A","Pantry",1000,"g",25,1),
("pep-a1","Black Pepper Powder","Brand A","Pantry",100,"g",60,1),
("cap-g1","Green Capsicum","Brand A","Produce",250,"g",40,1),("cap-r1","Red Capsicum","Brand A","Produce",250,"g",70,1),
("cor-a1","Sweet Corn Kernels","Brand A","Frozen",400,"g",80,1),("chf-a1","Chilli Flakes","Brand A","Pantry",50,"g",45,1),
("ita-a1","Italian Seasoning","Brand A","Pantry",25,"g",55,1),("ktc-a1","Tomato Ketchup","Brand A","Pantry",500,"g",110,1),
("pap-a1","Paprika Powder","Brand A","Pantry",50,"g",65,1),("chs-a1","Cheese Slices","Brand A","Dairy",10,"piece",130,1),
("car-a1","Carrot","Brand A","Produce",500,"g",35,1),("gin-a1","Fresh Ginger","Brand A","Produce",100,"g",20,1),("chl-a1","Fresh Green Chilli","Brand A","Produce",100,"g",15,1),
("cor-b1","Fresh Coriander Leaves","Brand A","Produce",100,"g",15,1),("cor-p1","Coriander Powder","Brand A","Pantry",100,"g",40,1),
("van-a1","Vanilla Extract","Brand A","Pantry",50,"ml",120,1),("sug-a1","Sugar","Brand A","Pantry",1000,"g",52,1),("sug-a2","Sugar","Brand A","Pantry",500,"g",28,1),
("bas-a1","Fresh Basil Leaves","Brand A","Produce",50,"g",35,1),
("chk-t1","Chicken Thigh Bone-in","Brand A","Meat",500,"g",210,1),("chk-t2","Chicken Thigh Boneless","Brand B","Meat",500,"g",260,1),("chk-dr","Chicken Drumsticks","Brand A","Meat",500,"g",190,1),
("btm-a1","Buttermilk (Chaas)","Brand A","Dairy",200,"ml",20,1),("crd-a1","Curd","Brand A","Dairy",400,"g",40,1),
("hot-a1","Hot Sauce","Brand A","Pantry",150,"ml",90,1),("hot-b1","Sriracha Chilli Sauce","Brand B","Pantry",200,"g",130,0),("hot-c1","Peri Peri Hot Sauce","Brand C","Pantry",175,"g",110,1),
("vin-a1","White Vinegar","Brand A","Pantry",500,"ml",35,1),("vin-b1","Apple Cider Vinegar","Brand B","Pantry",500,"ml",120,1),("vin-c1","Balsamic Vinegar","Brand C","Pantry",250,"ml",180,1),
("soy-a1","Dark Soy Sauce","Brand A","Pantry",150,"ml",60,1),("soy-b1","Soy Sauce","Brand B","Pantry",200,"ml",55,1),("soy-c1","Sweet Soy Sauce","Brand C","Pantry",250,"ml",95,1),
("hon-a1","Honey","Brand A","Pantry",250,"g",140,1),("may-a1","Mayonnaise","Brand A","Pantry",250,"g",95,1),("may-b1","Japanese Mayonnaise","Brand B","Pantry",210,"g",150,1),
("cab-a1","Green Cabbage","Brand A","Produce",500,"g",30,1),("kim-a1","Kimchi","Brand A","Pantry",300,"g",160,1),("sta-a1","Corn Starch","Brand A","Pantry",200,"g",45,1),
("chi-r1","Red Chilli Powder","Brand A","Pantry",100,"g",45,1),("onp-a1","Onion Powder","Brand A","Pantry",50,"g",55,1),("gap-a1","Garlic Powder","Brand A","Pantry",50,"g",60,1),
("bks-a1","Baking Soda","Brand A","Pantry",100,"g",25,1),("msg-a1","Monosodium Glutamate (MSG)","Brand A","Pantry",100,"g",30,1),("goc-a1","Gochujang Korean Chilli Paste","Brand A","Pantry",200,"g",220,1),
("jal-a1","Jalapeno Slices","Brand A","Pantry",340,"g",190,1),("dil-a1","Fresh Dill","Brand A","Produce",50,"g",40,1),
("mus-a1","Mustard Seeds","Brand A","Pantry",100,"g",30,1),("cha-a1","Chana Dal","Brand A","Pantry",500,"g",75,1),("urd-a1","Urad Dal Whole Black Gram","Brand A","Pantry",500,"g",95,1),
("cur-a1","Curry Leaves","Brand A","Produce",50,"g",10,1),("cas-a1","Cashew Nuts","Brand A","Pantry",100,"g",120,1),("pea-a1","Peanuts","Brand A","Pantry",500,"g",90,1),("tur-a1","Turmeric Powder","Brand A","Pantry",100,"g",35,1),
("oil-s1","Sunflower Oil","Brand A","Pantry",1000,"ml",150,1),("oil-r1","Refined Soyabean Oil","Brand B","Pantry",1000,"ml",140,1),("oil-g1","Groundnut Oil","Brand C","Pantry",1000,"ml",210,1),("oil-m1","Mustard Oil","Brand D","Pantry",500,"ml",110,1),
("wpe-a1","White Pepper Powder","Brand A","Pantry",50,"g",70,1),("lem-a1","Lemon","Brand A","Produce",250,"g",30,1),("lim-a1","Lime","Brand B","Produce",250,"g",35,1),
("spo-a1","Spring Onion","Brand A","Produce",250,"g",25,1),("wat-a1","Packaged Drinking Water","Brand A","Pantry",1000,"ml",20,1),("pot-a1","Potato","Brand A","Produce",1000,"g",40,1)]
CATALOG = {r[0]: dict(product_id=r[0], name=r[1], brand=r[2], category=r[3], variant=None, pack_quantity=r[4],
                      pack_unit=r[5], price=float(r[6]), availability=bool(r[7]), image_url=None) for r in _C}


def _item(p, packs): return {"product_id": p["product_id"], "name": f'{p["name"]} ({p["brand"]}, {p["pack_quantity"]:g} {p["pack_unit"]})',
                              "packs": packs, "price": p["price"]}


class LocalInstamartMCPClient:
    label = "LOCAL INSTAMART MCP DEVELOPMENT MODE — mock catalog, not real Instamart prices"

    def __init__(self): self.carts = {}

    async def addresses(self, sid=None): return [{"id": "demo-1", "label": "Demo address (local mock catalog)"}]

    async def search(self, q, address_id=None, sid=None):
        ws = [engine.sing(w) for w in engine.words(q)]
        subs = [s for k, v in engine.SUBS.items() if k in ws for s in v]
        eq = engine._equiv(" ".join(ws)); phr = [{engine.sing(w) for w in engine.words(p)} for p in (eq[0] if eq else [])]

        def run(qt, subs):
            out = []
            for p in CATALOG.values():
                text = p["name"].lower(); pt = {engine.sing(w) for w in engine.words(text)}
                if qt and (qt <= pt or any(s in text for s in subs) or any(ph <= pt for ph in phr)): out.append(p)
            return out
        return run(set(ws), subs) or (run({ws[-1]}, []) if ws else [])  # fall back to the head noun, like a fuzzy store search

    async def known(self, pid, sid=None): return CATALOG.get(pid)

    async def revalidate(self, pid, sid=None, address_id=None): return CATALOG.get(pid)  # static mock catalog: same as known

    async def get_cart(self, sid):
        if sid not in self.carts:
            if len(self.carts) > 1000: self.carts.clear()
            self.carts[sid] = [_item(CATALOG["milk-001"], 1), _item(CATALOG["brd-001"], 1)]
        return [dict(i) for i in self.carts[sid]]

    async def clear_cart(self, sid): self.carts[sid] = []

    async def update_cart(self, sid, items, address_id=None): self.carts[sid] = [dict(i) for i in items]


def make_client(mode):
    if mode == "swiggy":
        import swiggy
        return swiggy.SwiggyInstamartMCPClient()
    return LocalInstamartMCPClient()

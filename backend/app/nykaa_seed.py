"""Nykaa Pulse — Phase 1 catalog seed data.

Populates the np_categories / np_brands / np_subcategories /
np_sub_subcategories / np_products tables (see nykaa_store.py) with a fixed
taxonomy of 10 categories, 4 brands per category, 4 subcategories per
category, 2 sub-subcategories per subcategory, and ~2 products per
sub-subcategory (roughly 160 products total).

seed_catalog() is idempotent-safe to call on every app startup: it checks
nykaa_store.catalog_is_seeded() first and no-ops if the catalog already has
data. The underlying insert_* helpers are themselves idempotent upserts, so
even a partial/duplicate run would not create duplicate rows — the startup
check is just there to avoid the (much slower) redundant round of upserts.
"""
from . import nykaa_store


def seed_catalog() -> None:
    if nykaa_store.catalog_is_seeded():
        return

    _seed_makeup()
    _seed_skincare()
    _seed_hair_care()
    _seed_bath_body()
    _seed_fragrance()
    _seed_mens_grooming()
    _seed_beauty_tools()
    _seed_wellness()
    _seed_personal_care()
    _seed_nail_care()


def _insert_products(category_id: int, rows: list[tuple]) -> None:
    """rows: (brand_id, subcategory_id, sub_subcategory_id, name, description,
    price_inr, details, positive_themes, negative_themes)"""
    for brand_id, subcategory_id, sub_subcategory_id, name, description, price_inr, details, positive_themes, negative_themes in rows:
        nykaa_store.insert_product(
            category_id, brand_id, subcategory_id, sub_subcategory_id,
            name, description, price_inr, details, positive_themes, negative_themes,
        )


# ---- Makeup ------------------------------------------------------------------

def _seed_makeup() -> None:
    category_id = nykaa_store.insert_category("Makeup")

    maybelline = nykaa_store.insert_brand("Maybelline")
    lakme = nykaa_store.insert_brand("Lakmé")
    nykaa_cosmetics = nykaa_store.insert_brand("Nykaa Cosmetics")
    loreal = nykaa_store.insert_brand("L'Oréal Paris")

    lip = nykaa_store.insert_subcategory(category_id, "Lip Makeup")
    face = nykaa_store.insert_subcategory(category_id, "Face Makeup")
    eye = nykaa_store.insert_subcategory(category_id, "Eye Makeup")
    cheek = nykaa_store.insert_subcategory(category_id, "Cheek Makeup")

    liquid_lipstick = nykaa_store.insert_sub_subcategory(lip, "Liquid Lipstick")
    bullet_lipstick = nykaa_store.insert_sub_subcategory(lip, "Bullet Lipstick")
    foundation = nykaa_store.insert_sub_subcategory(face, "Foundation")
    compact_powder = nykaa_store.insert_sub_subcategory(face, "Compact Powder")
    mascara = nykaa_store.insert_sub_subcategory(eye, "Mascara")
    eyeliner = nykaa_store.insert_sub_subcategory(eye, "Eyeliner")
    blush = nykaa_store.insert_sub_subcategory(cheek, "Blush")
    highlighter = nykaa_store.insert_sub_subcategory(cheek, "Highlighter")

    rows = [
        (maybelline, lip, liquid_lipstick, "Super Stay Matte Ink", "Long-lasting matte liquid lipstick", 699,
         {"shade": "Pioneer Red", "finish": "Matte", "transfer_proof": "Yes", "size": "5ml"},
         ["Long-lasting", "Highly Pigmented", "Transfer-proof", "Comfortable"],
         ["Drying", "Sticky", "Shade Mismatch", "Patchy"]),
        (maybelline, lip, liquid_lipstick, "Vinyl Ink", "Glossy long-wear liquid lipstick", 749,
         {"shade": "Peachy Nude", "finish": "Glossy", "non_sticky": "Yes", "size": "5ml"},
         ["Glossy Finish", "Smooth Application", "Hydrating"],
         ["Transfers", "Expensive", "Sticky"]),
        (nykaa_cosmetics, lip, bullet_lipstick, "Matte To Last", "Comfortable everyday matte lipstick", 599,
         {"shade": "Bombae", "finish": "Matte", "vitamin_e": "Yes"},
         ["Rich Color", "Lightweight", "Moisturizing"],
         ["Fades Quickly", "Drying", "Patchy"]),
        (loreal, lip, bullet_lipstick, "Color Riche Bullet Lipstick", "Creamy satin-finish bullet lipstick", 649,
         {"shade": "Coral Sunset", "finish": "Satin"},
         ["Creamy Texture", "Rich Pigment", "Comfortable Wear"],
         ["Fades After Meals", "Expensive", "Limited Shades"]),
        (loreal, face, foundation, "Infallible 24H Foundation", "Full coverage liquid foundation", 899,
         {"shade": "Golden Beige", "coverage": "Full", "finish": "Matte"},
         ["Blendable", "Good Coverage", "Long Wear"],
         ["Oxidizes", "Heavy", "Cakes"]),
        (maybelline, face, foundation, "Fit Me Matte Foundation", "Lightweight matte foundation", 649,
         {"shade": "128 Warm Nude", "coverage": "Medium", "skin_type": "Oily"},
         ["Natural Finish", "Lightweight", "Doesn't Oxidize"],
         ["Wrong Shade", "Dry Patches", "Pump Issue"]),
        (lakme, face, foundation, "9to5 Primer + Matte", "Primer-infused foundation", 575,
         {"shade": "Warm Beige", "coverage": "Medium"},
         ["Smooth Finish", "Buildable Coverage"],
         ["Heavy", "Oxidizes", "Expensive"]),
        (lakme, face, compact_powder, "Perfect Definition Compact", "Oil-control compact", 275,
         {"shade": "Natural", "finish": "Matte"},
         ["Oil Control", "Smooth Finish", "Lightweight"],
         ["Chalky", "Breaks Easily", "Powdery"]),
        (nykaa_cosmetics, face, compact_powder, "SkinShield Matte Compact", "Oil-control matte compact powder", 499,
         {"shade": "Ivory", "finish": "Matte"},
         ["Oil Control", "Lightweight", "Long Lasting"],
         ["Chalky Finish", "Expensive", "Cakey On Dry Skin"]),
        (maybelline, eye, mascara, "Lash Sensational Sky High", "Lengthening mascara", 799,
         {"color": "Black", "waterproof": "Yes"},
         ["Lengthening", "Volumizing", "Waterproof"],
         ["Clumps", "Smudges", "Difficult Removal"]),
        (loreal, eye, mascara, "Volume Million Lashes", "Volumizing mascara", 899,
         {"color": "Black", "waterproof": "Yes"},
         ["Thick Lashes", "Long Lasting"],
         ["Flakes", "Smudges", "Dries Fast"]),
        (lakme, eye, eyeliner, "Eyeconic Liner", "Waterproof liquid eyeliner", 399,
         {"color": "Deep Black", "waterproof": "Yes"},
         ["Precise Tip", "Rich Color", "Long Wear"],
         ["Smears", "Fades", "Irritates Eyes"]),
        (nykaa_cosmetics, eye, eyeliner, "Ink It Up Gel Eyeliner Pen", "Smudge-proof gel eyeliner pen", 399,
         {"color": "Black", "waterproof": "Yes"},
         ["Precise Application", "Long Lasting", "Smudge-Proof"],
         ["Dries Out Fast", "Expensive", "Skips On Application"]),
        (lakme, cheek, blush, "Rose Face Blush", "Natural-finish pressed powder blush", 375,
         {"shade": "Pink Blossom", "finish": "Matte"},
         ["Natural Flush", "Blendable", "Affordable"],
         ["Low Pigmentation", "Powdery Fallout", "Fades Fast"]),
        (nykaa_cosmetics, cheek, blush, "SoftMatte Blush", "Buildable matte powder blush", 450,
         {"shade": "Peach Fuzz", "finish": "Matte"},
         ["Buildable Color", "Soft Texture", "Long Lasting"],
         ["Expensive", "Chalky", "Hard To Blend"]),
        (maybelline, cheek, highlighter, "Face Studio Master Chrome Highlighter", "Liquid metallic highlighter", 699,
         {"shade": "Molten Rose Gold", "finish": "Shimmer"},
         ["Intense Glow", "Blendable", "Long Lasting"],
         ["Too Shimmery", "Expensive", "Fallout Issue"]),
        (loreal, cheek, highlighter, "Glow Highlighter", "Radiance-boosting powder highlighter", 799,
         {"shade": "Golden Sand", "finish": "Shimmer"},
         ["Natural Glow", "Smooth Texture", "Buildable"],
         ["Expensive", "Chunky Glitter", "Fades By Evening"]),
    ]
    _insert_products(category_id, rows)


# ---- Skincare ------------------------------------------------------------------

def _seed_skincare() -> None:
    category_id = nykaa_store.insert_category("Skincare")

    cetaphil = nykaa_store.insert_brand("Cetaphil")
    dot_key = nykaa_store.insert_brand("Dot & Key")
    minimalist = nykaa_store.insert_brand("Minimalist")
    neutrogena = nykaa_store.insert_brand("Neutrogena")

    cleansers = nykaa_store.insert_subcategory(category_id, "Cleansers")
    moisturizers = nykaa_store.insert_subcategory(category_id, "Moisturizers")
    serums = nykaa_store.insert_subcategory(category_id, "Serums")
    sunscreens = nykaa_store.insert_subcategory(category_id, "Sunscreens")

    gel_cleanser = nykaa_store.insert_sub_subcategory(cleansers, "Gel Cleanser")
    foam_cleanser = nykaa_store.insert_sub_subcategory(cleansers, "Foam Cleanser")
    gel_moisturizer = nykaa_store.insert_sub_subcategory(moisturizers, "Gel Moisturizer")
    cream_moisturizer = nykaa_store.insert_sub_subcategory(moisturizers, "Cream Moisturizer")
    vitamin_c_serum = nykaa_store.insert_sub_subcategory(serums, "Vitamin C Serum")
    niacinamide_serum = nykaa_store.insert_sub_subcategory(serums, "Niacinamide Serum")
    gel_sunscreen = nykaa_store.insert_sub_subcategory(sunscreens, "Gel Sunscreen")
    matte_sunscreen = nykaa_store.insert_sub_subcategory(sunscreens, "Matte Sunscreen")

    rows = [
        (cetaphil, cleansers, gel_cleanser, "Gentle Skin Cleanser", "Soap-free gentle daily cleanser", 550,
         {"skin_type": "Sensitive", "size": "125ml"},
         ["Gentle On Skin", "Non-Drying", "Fragrance-Free", "Soap-Free"],
         ["Expensive", "Doesn't Foam", "Packaging Leaks"]),
        (neutrogena, cleansers, gel_cleanser, "Deep Clean Gel Cleanser", "Oil-clearing gel face cleanser", 375,
         {"skin_type": "Oily", "size": "100ml"},
         ["Deep Cleansing", "Fresh Feel", "Removes Oil"],
         ["Drying", "Stings Eyes", "Strong Fragrance"]),
        (dot_key, cleansers, foam_cleanser, "Vitamin C Foaming Cleanser", "Brightening vitamin C foam cleanser", 495,
         {"skin_type": "All", "size": "135ml"},
         ["Brightens Skin", "Gentle Foam", "Pleasant Scent"],
         ["Expensive", "Small Bottle", "Runs Out Fast"]),
        (minimalist, cleansers, foam_cleanser, "Salicylic Acid Foam Cleanser", "Acne-control salicylic acid cleanser", 425,
         {"skin_type": "Acne-Prone", "size": "100ml"},
         ["Controls Acne", "Lightweight", "Non-Comedogenic"],
         ["Purging Phase", "Drying", "Slow Results"]),
        (dot_key, moisturizers, gel_moisturizer, "Watermelon Gel Moisturizer", "Lightweight hydrating gel moisturizer", 595,
         {"skin_type": "Oily", "size": "50g"},
         ["Lightweight", "Hydrating", "Absorbs Quickly"],
         ["Expensive", "Sticky Residue", "Small Quantity"]),
        (neutrogena, moisturizers, gel_moisturizer, "Hydro Boost Gel Moisturizer", "Water-gel formula for deep hydration", 699,
         {"skin_type": "Combination", "size": "50g"},
         ["Deep Hydration", "Non-Greasy", "Fast Absorbing"],
         ["Pricey", "Thin Consistency", "Packaging Issue"]),
        (cetaphil, moisturizers, cream_moisturizer, "Moisturizing Cream", "Rich daily moisturizing cream", 650,
         {"skin_type": "Dry", "size": "100g"},
         ["Rich Texture", "Long-Lasting", "Fragrance-Free"],
         ["Greasy Feel", "Heavy For Day", "Slow Absorption"]),
        (minimalist, moisturizers, cream_moisturizer, "Ceramide Barrier Repair Cream", "Ceramide-based barrier repair cream", 575,
         {"skin_type": "Dry", "size": "50g"},
         ["Repairs Barrier", "Soothing", "Non-Irritating"],
         ["Expensive", "Greasy", "Strong Smell"]),
        (minimalist, serums, vitamin_c_serum, "10% Vitamin C Serum", "Brightening vitamin C face serum", 599,
         {"skin_type": "All", "size": "30ml"},
         ["Brightens Skin", "Evens Tone", "Lightweight"],
         ["Oxidizes Fast", "Tingling Sensation", "Sticky"]),
        (dot_key, serums, vitamin_c_serum, "Vitamin C Serum", "Glow-boosting vitamin C serum", 795,
         {"skin_type": "Dull Skin", "size": "30ml"},
         ["Visible Glow", "Fast Absorbing", "Good Packaging"],
         ["Expensive", "Delayed Results", "Strong Smell"]),
        (minimalist, serums, niacinamide_serum, "10% Niacinamide Serum", "Pore-refining niacinamide serum", 549,
         {"skin_type": "Acne-Prone", "size": "30ml"},
         ["Reduces Breakouts", "Minimizes Pores", "Lightweight"],
         ["Slow Results", "Purging", "Sticky Texture"]),
        (cetaphil, serums, niacinamide_serum, "Niacinamide Serum", "Soothing niacinamide serum for sensitive skin", 699,
         {"skin_type": "Sensitive", "size": "30ml"},
         ["Calms Redness", "Gentle Formula", "Non-Irritating"],
         ["Expensive", "Thin Bottle", "Slow Absorption"]),
        (neutrogena, sunscreens, gel_sunscreen, "Ultra Sheer Gel Sunscreen", "Lightweight broad-spectrum gel sunscreen", 549,
         {"spf": "50", "finish": "Matte"},
         ["Lightweight", "No White Cast", "Non-Greasy"],
         ["Expensive", "Runs Into Eyes", "White Cast In Sun"]),
        (dot_key, sunscreens, gel_sunscreen, "Vitamin C Gel Sunscreen", "Hydrating vitamin C sunscreen gel", 595,
         {"spf": "50", "finish": "Dewy"},
         ["Hydrating", "Blends Easily", "Pleasant Scent"],
         ["Pricey", "Sticky", "Small Tube"]),
        (minimalist, sunscreens, matte_sunscreen, "SPF 50 Matte Sunscreen", "Matte-finish broad-spectrum sunscreen", 549,
         {"spf": "50", "finish": "Matte"},
         ["Matte Finish", "No White Cast", "Non-Sticky"],
         ["Expensive", "Thick Texture", "Breakouts"]),
        (cetaphil, sunscreens, matte_sunscreen, "Sun SPF 50+ Matte Sunscreen", "Non-comedogenic matte sunscreen", 625,
         {"spf": "50+", "finish": "Matte"},
         ["Broad Spectrum", "Non-Comedogenic", "Long Lasting"],
         ["Greasy Initially", "Expensive", "Strong Smell"]),
    ]
    _insert_products(category_id, rows)


# ---- Hair Care ------------------------------------------------------------------

def _seed_hair_care() -> None:
    category_id = nykaa_store.insert_category("Hair Care")

    loreal = nykaa_store.insert_brand("L'Oréal Paris")
    dove = nykaa_store.insert_brand("Dove")
    mamaearth = nykaa_store.insert_brand("Mamaearth")
    bblunt = nykaa_store.insert_brand("BBlunt")

    shampoo = nykaa_store.insert_subcategory(category_id, "Shampoo")
    conditioner = nykaa_store.insert_subcategory(category_id, "Conditioner")
    hair_oil = nykaa_store.insert_subcategory(category_id, "Hair Oil")
    hair_styling = nykaa_store.insert_subcategory(category_id, "Hair Styling")

    repair_shampoo = nykaa_store.insert_sub_subcategory(shampoo, "Repair Shampoo")
    anti_dandruff_shampoo = nykaa_store.insert_sub_subcategory(shampoo, "Anti-Dandruff Shampoo")
    smooth_conditioner = nykaa_store.insert_sub_subcategory(conditioner, "Smooth Conditioner")
    repair_conditioner = nykaa_store.insert_sub_subcategory(conditioner, "Repair Conditioner")
    hair_growth_oil = nykaa_store.insert_sub_subcategory(hair_oil, "Hair Growth Oil")
    nourishing_oil = nykaa_store.insert_sub_subcategory(hair_oil, "Nourishing Oil")
    heat_protect_spray = nykaa_store.insert_sub_subcategory(hair_styling, "Heat Protect Spray")
    hair_spray = nykaa_store.insert_sub_subcategory(hair_styling, "Hair Spray")

    rows = [
        (loreal, shampoo, repair_shampoo, "Total Repair 5 Shampoo", "Damage-repair shampoo for weak hair", 399,
         {"hair_type": "Damaged", "size": "340ml"},
         ["Repairs Damage", "Smooth Hair", "Nice Fragrance"],
         ["Contains Sulphates", "Drying", "Weighs Hair Down"]),
        (mamaearth, shampoo, repair_shampoo, "Onion Repair Shampoo", "Onion-extract shampoo to reduce hairfall", 349,
         {"hair_type": "Damaged", "size": "250ml"},
         ["Reduces Hairfall", "Natural Ingredients", "Good Lather"],
         ["Strong Onion Smell", "Drying", "Expensive For Size"]),
        (dove, shampoo, anti_dandruff_shampoo, "Anti-Dandruff Shampoo", "Daily anti-dandruff shampoo", 275,
         {"hair_type": "Dandruff-Prone", "size": "340ml"},
         ["Controls Dandruff", "Soft Hair", "Affordable"],
         ["Doesn't Fully Cure Dandruff", "Fragrance Fades", "Thin Formula"]),
        (bblunt, shampoo, anti_dandruff_shampoo, "Anti-Dandruff Shampoo", "Salon-grade anti-dandruff shampoo", 425,
         {"hair_type": "Oily Scalp", "size": "300ml"},
         ["Salon Quality", "Fresh Scalp", "Long-Lasting"],
         ["Expensive", "Hard To Find", "Strong Menthol"]),
        (dove, conditioner, smooth_conditioner, "Intense Repair Conditioner", "Smoothing daily conditioner", 299,
         {"hair_type": "Frizzy", "size": "175ml"},
         ["Smooths Hair", "Detangles Easily", "Affordable"],
         ["Weighs Hair Down", "Greasy Roots", "Small Bottle"]),
        (loreal, conditioner, smooth_conditioner, "Smooth Intense Conditioner", "Frizz-control smoothing conditioner", 375,
         {"hair_type": "Frizzy", "size": "175ml"},
         ["Silky Finish", "Reduces Frizz", "Pleasant Smell"],
         ["Pricey", "Heavy For Fine Hair", "Needs Frequent Use"]),
        (mamaearth, conditioner, repair_conditioner, "Onion Conditioner", "Onion-extract conditioner for damaged hair", 329,
         {"hair_type": "Damaged", "size": "200ml"},
         ["Reduces Breakage", "Natural Formula", "Soft Hair"],
         ["Onion Smell", "Greasy", "Expensive"]),
        (bblunt, conditioner, repair_conditioner, "Intense Moisture Conditioner", "Deep-conditioning treatment for dry hair", 450,
         {"hair_type": "Dry", "size": "200ml"},
         ["Deep Conditioning", "Salon Finish", "Smooth Result"],
         ["Expensive", "Hard To Rinse", "Limited Availability"]),
        (mamaearth, hair_oil, hair_growth_oil, "Onion Hair Growth Oil", "Onion oil blend to reduce hairfall", 399,
         {"hair_type": "Thinning", "size": "150ml"},
         ["Reduces Hairfall", "Promotes Growth", "Natural Ingredients"],
         ["Strong Smell", "Greasy", "Slow Results"]),
        (bblunt, hair_oil, hair_growth_oil, "Back To Life Hair Growth Oil", "Lightweight hair growth oil", 499,
         {"hair_type": "Thinning", "size": "100ml"},
         ["Lightweight", "Non-Sticky", "Nice Fragrance"],
         ["Expensive", "Small Bottle", "Delayed Results"]),
        (dove, hair_oil, nourishing_oil, "Nourishing Hair Oil", "Daily nourishing hair oil", 199,
         {"hair_type": "Dry", "size": "200ml"},
         ["Nourishes Hair", "Affordable", "Non-Sticky"],
         ["Mild Effect", "Thin Consistency", "Common Fragrance"]),
        (loreal, hair_oil, nourishing_oil, "Extraordinary Oil", "Shine-boosting non-sticky hair oil", 549,
         {"hair_type": "Frizzy", "size": "100ml"},
         ["Adds Shine", "Lightweight", "Tames Frizz"],
         ["Expensive", "Small Bottle", "Greasy If Overused"]),
        (loreal, hair_styling, heat_protect_spray, "Heat Protect Spray", "Thermal protection styling spray", 499,
         {"hair_type": "All", "size": "150ml"},
         ["Protects From Heat", "Lightweight", "Adds Shine"],
         ["Expensive", "Sticky Residue", "Strong Fragrance"]),
        (bblunt, hair_styling, heat_protect_spray, "Heat Protection Spray", "Salon heat-protectant spray", 525,
         {"hair_type": "Color-Treated", "size": "150ml"},
         ["Salon Quality", "Protects Color", "Smooth Finish"],
         ["Pricey", "Small Bottle", "Greasy Feel"]),
        (dove, hair_styling, hair_spray, "Style Care Hair Spray", "Medium-hold everyday hair spray", 299,
         {"hold": "Medium", "size": "200ml"},
         ["Flexible Hold", "Non-Sticky", "Affordable"],
         ["Weak Hold", "Strong Smell", "Flakes"]),
        (mamaearth, hair_styling, hair_spray, "Styling Hair Spray", "Strong-hold natural hair spray", 349,
         {"hold": "Strong", "size": "150ml"},
         ["Strong Hold", "Natural Ingredients", "Long Lasting"],
         ["Sticky", "Stiff Feel", "Hard To Wash Out"]),
    ]
    _insert_products(category_id, rows)


# ---- Bath & Body ------------------------------------------------------------------

def _seed_bath_body() -> None:
    category_id = nykaa_store.insert_category("Bath & Body")

    nivea = nykaa_store.insert_brand("NIVEA")
    dove = nykaa_store.insert_brand("Dove")
    body_shop = nykaa_store.insert_brand("The Body Shop")
    vaseline = nykaa_store.insert_brand("Vaseline")

    body_wash = nykaa_store.insert_subcategory(category_id, "Body Wash")
    body_lotion = nykaa_store.insert_subcategory(category_id, "Body Lotion")
    body_scrub = nykaa_store.insert_subcategory(category_id, "Body Scrub")
    hand_care = nykaa_store.insert_subcategory(category_id, "Hand Care")

    shower_gel = nykaa_store.insert_sub_subcategory(body_wash, "Shower Gel")
    cream_body_wash = nykaa_store.insert_sub_subcategory(body_wash, "Cream Body Wash")
    daily_lotion = nykaa_store.insert_sub_subcategory(body_lotion, "Daily Lotion")
    body_butter = nykaa_store.insert_sub_subcategory(body_lotion, "Body Butter")
    coffee_scrub = nykaa_store.insert_sub_subcategory(body_scrub, "Coffee Scrub")
    sugar_scrub = nykaa_store.insert_sub_subcategory(body_scrub, "Sugar Scrub")
    hand_cream = nykaa_store.insert_sub_subcategory(hand_care, "Hand Cream")
    hand_wash = nykaa_store.insert_sub_subcategory(hand_care, "Hand Wash")

    rows = [
        (nivea, body_wash, shower_gel, "Fresh Blossom Shower Gel", "Fresh floral daily shower gel", 199,
         {"skin_type": "All", "size": "250ml"},
         ["Fresh Fragrance", "Rich Lather", "Affordable"],
         ["Drying", "Fragrance Fades", "Runny Formula"]),
        (dove, body_wash, shower_gel, "Deeply Nourishing Shower Gel", "Moisturizing cream-based shower gel", 225,
         {"skin_type": "Dry", "size": "250ml"},
         ["Moisturizing", "Creamy Lather", "Gentle On Skin"],
         ["Expensive For Size", "Slippery Cap", "Mild Fragrance"]),
        (body_shop, body_wash, cream_body_wash, "Vitamin E Cream Body Wash", "Nourishing vitamin E cream wash", 595,
         {"skin_type": "Dry", "size": "250ml"},
         ["Rich Texture", "Nourishing", "Pleasant Scent"],
         ["Expensive", "Thick To Rinse", "Small Bottle"]),
        (vaseline, body_wash, cream_body_wash, "Healthy Moisture Cream Body Wash", "Deep-moisture daily body wash", 249,
         {"skin_type": "Dry", "size": "245ml"},
         ["Deep Moisture", "Affordable", "Soft Skin"],
         ["Weak Fragrance", "Runny", "Doesn't Lather Much"]),
        (vaseline, body_lotion, daily_lotion, "Intensive Care Daily Lotion", "Fast-absorbing daily body lotion", 199,
         {"skin_type": "Dry", "size": "200ml"},
         ["Fast Absorbing", "Long-Lasting Moisture", "Affordable"],
         ["Sticky Feel", "Strong Smell", "Thick Texture"]),
        (nivea, body_lotion, daily_lotion, "Nourishing Daily Lotion", "Lightweight everyday body lotion", 225,
         {"skin_type": "Normal", "size": "200ml"},
         ["Lightweight", "Non-Greasy", "Good Fragrance"],
         ["Mild Moisturization", "Runs Out Fast", "Pump Issue"]),
        (body_shop, body_lotion, body_butter, "Shea Body Butter", "Rich shea butter for dry skin", 1495,
         {"skin_type": "Dry", "size": "200ml"},
         ["Rich Moisture", "Luxurious Feel", "Long-Lasting"],
         ["Expensive", "Greasy", "Heavy Fragrance"]),
        (dove, body_lotion, body_butter, "Deeply Nourishing Body Butter", "Deeply hydrating body butter", 450,
         {"skin_type": "Dry", "size": "150ml"},
         ["Deep Hydration", "Non-Greasy", "Soft Skin"],
         ["Pricey", "Thick To Spread", "Small Jar"]),
        (body_shop, body_scrub, coffee_scrub, "Coffee Body Scrub", "Exfoliating coffee bean scrub", 1595,
         {"skin_type": "All", "size": "200ml"},
         ["Exfoliates Well", "Pleasant Aroma", "Smooth Skin"],
         ["Expensive", "Messy Application", "Gritty Residue"]),
        (nivea, body_scrub, coffee_scrub, "Coffee Body Scrub", "Energizing coffee exfoliating scrub", 399,
         {"skin_type": "All", "size": "200g"},
         ["Affordable", "Good Exfoliation", "Nice Scent"],
         ["Rough Texture", "Drying", "Messy"]),
        (body_shop, body_scrub, sugar_scrub, "Sugar Body Scrub", "Gentle exfoliating sugar scrub", 1450,
         {"skin_type": "Dry", "size": "200ml"},
         ["Gentle Exfoliation", "Moisturizing", "Lovely Fragrance"],
         ["Expensive", "Small Jar", "Oily Residue"]),
        (vaseline, body_scrub, sugar_scrub, "Sugar Body Polish", "Softening sugar body polish", 299,
         {"skin_type": "All", "size": "150g"},
         ["Affordable", "Softens Skin", "Easy Rinse"],
         ["Mild Exfoliation", "Runny", "Weak Fragrance"]),
        (vaseline, hand_care, hand_cream, "Intensive Care Hand Cream", "Fast-absorbing daily hand cream", 149,
         {"skin_type": "Dry", "size": "75ml"},
         ["Fast Absorbing", "Affordable", "Long-Lasting"],
         ["Sticky", "Small Tube", "Strong Smell"]),
        (nivea, hand_care, hand_cream, "Repair Care Hand Cream", "Deep-nourishing hand repair cream", 175,
         {"skin_type": "Dry", "size": "75ml"},
         ["Deep Nourishment", "Non-Greasy", "Affordable"],
         ["Runs Out Fast", "Mild Fragrance", "Tube Leaks"]),
        (dove, hand_care, hand_wash, "Care & Protect Hand Wash", "Gentle daily hand wash", 99,
         {"size": "200ml"},
         ["Gentle Formula", "Good Fragrance", "Affordable"],
         ["Weak Lather", "Runny", "Pump Breaks"]),
        (nivea, hand_care, hand_wash, "Milk Delights Hand Wash", "Moisturizing milk-extract hand wash", 129,
         {"size": "200ml"},
         ["Moisturizing", "Nice Fragrance", "Affordable"],
         ["Thin Formula", "Fragrance Fades", "Pump Issue"]),
    ]
    _insert_products(category_id, rows)


# ---- Fragrance ------------------------------------------------------------------

def _seed_fragrance() -> None:
    category_id = nykaa_store.insert_category("Fragrance")

    bella_vita = nykaa_store.insert_brand("Bella Vita")
    skinn = nykaa_store.insert_brand("SKINN by Titan")
    engage = nykaa_store.insert_brand("Engage")
    carlton_london = nykaa_store.insert_brand("Carlton London")

    perfumes = nykaa_store.insert_subcategory(category_id, "Perfumes")
    deodorants = nykaa_store.insert_subcategory(category_id, "Deodorants")
    body_mist = nykaa_store.insert_subcategory(category_id, "Body Mist")
    gift_sets = nykaa_store.insert_subcategory(category_id, "Gift Sets")

    edp = nykaa_store.insert_sub_subcategory(perfumes, "Eau de Parfum")
    edt = nykaa_store.insert_sub_subcategory(perfumes, "Eau de Toilette")
    roll_on = nykaa_store.insert_sub_subcategory(deodorants, "Roll-On")
    spray = nykaa_store.insert_sub_subcategory(deodorants, "Spray")
    floral_mist = nykaa_store.insert_sub_subcategory(body_mist, "Floral Mist")
    fruity_mist = nykaa_store.insert_sub_subcategory(body_mist, "Fruity Mist")
    mens_gift_set = nykaa_store.insert_sub_subcategory(gift_sets, "Men's Gift Set")
    womens_gift_set = nykaa_store.insert_sub_subcategory(gift_sets, "Women's Gift Set")

    rows = [
        (bella_vita, perfumes, edp, "Luxury Man EDP", "Long-lasting woody eau de parfum", 899,
         {"size": "50ml", "fragrance_family": "Woody"},
         ["Long Lasting", "Rich Fragrance", "Elegant Bottle"],
         ["Overpowering", "Fades By Evening", "Expensive"]),
        (skinn, perfumes, edp, "Celeste EDP", "Premium floral eau de parfum", 1450,
         {"size": "50ml", "fragrance_family": "Floral"},
         ["Premium Smell", "Long Lasting", "Nice Packaging"],
         ["Expensive", "Sillage Too Strong", "Small Bottle"]),
        (carlton_london, perfumes, edt, "Signature EDT", "Fresh citrus eau de toilette", 599,
         {"size": "100ml", "fragrance_family": "Citrus"},
         ["Fresh Scent", "Affordable", "Good Sillage"],
         ["Short Lasting", "Weak In Summer", "Alcohol Smell"]),
        (engage, perfumes, edt, "Man EDT", "Everyday citrus eau de toilette", 499,
         {"size": "90ml", "fragrance_family": "Citrus"},
         ["Fresh Fragrance", "Affordable", "Everyday Wear"],
         ["Fades Quickly", "Weak Sillage", "Common Scent"]),
        (engage, deodorants, roll_on, "Roll-On Deodorant", "Long-lasting roll-on deodorant", 149,
         {"size": "50ml"},
         ["Long Lasting", "Affordable", "Pleasant Smell"],
         ["Sticky Feel", "Stains Clothes", "Mild Fragrance"]),
        (bella_vita, deodorants, roll_on, "Roll-On Deodorant", "Smooth-glide roll-on deodorant", 199,
         {"size": "50ml"},
         ["Smooth Application", "Good Fragrance", "Affordable"],
         ["Leaves Residue", "Short Lasting", "Sticky"]),
        (engage, deodorants, spray, "Deo Spray", "All-day freshness deodorant spray", 199,
         {"size": "150ml"},
         ["Long Lasting", "Fresh Scent", "Affordable"],
         ["Strong Spray", "Skin Irritation", "Overpowering"]),
        (carlton_london, deodorants, spray, "Deo Spray", "Long-lasting fragrance deodorant spray", 249,
         {"size": "150ml"},
         ["Good Fragrance", "Long Lasting", "Value For Money"],
         ["Gas Pressure Issue", "Overpowering", "Fades Fast"]),
        (bella_vita, body_mist, floral_mist, "Floral Body Mist", "Light floral daily body mist", 349,
         {"size": "200ml", "fragrance_family": "Floral"},
         ["Light Fragrance", "Refreshing", "Affordable"],
         ["Doesn't Last Long", "Weak Sillage", "Common Scent"]),
        (skinn, body_mist, floral_mist, "Rose Body Mist", "Elegant rose-scented body mist", 599,
         {"size": "150ml", "fragrance_family": "Floral"},
         ["Elegant Scent", "Refreshing", "Nice Bottle"],
         ["Expensive", "Fades Fast", "Small Size"]),
        (bella_vita, body_mist, fruity_mist, "Fruity Body Mist", "Refreshing fruity body mist", 349,
         {"size": "200ml", "fragrance_family": "Fruity"},
         ["Fresh Fragrance", "Fun Scent", "Affordable"],
         ["Short Lasting", "Weak Sillage", "Sticky"]),
        (carlton_london, body_mist, fruity_mist, "Fruity Body Mist", "Everyday fruity fragrance mist", 399,
         {"size": "200ml", "fragrance_family": "Fruity"},
         ["Pleasant Smell", "Affordable", "Everyday Use"],
         ["Fades Quickly", "Common Scent", "Weak Spray"]),
        (bella_vita, gift_sets, mens_gift_set, "Men's Grooming Gift Set", "Perfume and grooming gift combo", 1299,
         {"contents": "Perfume + Deo + Soap"},
         ["Great Value", "Nice Packaging", "Good For Gifting"],
         ["Expensive", "Small Quantities", "Mismatched Scents"]),
        (skinn, gift_sets, mens_gift_set, "Men's Gift Set", "Premium perfume and deo gift set", 1899,
         {"contents": "Perfume + Deo"},
         ["Premium Packaging", "Great Gift Option", "Long Lasting"],
         ["Expensive", "Limited Availability", "Overpowering Scent"]),
        (carlton_london, gift_sets, womens_gift_set, "Women's Gift Set", "Perfume and body mist gift set", 1399,
         {"contents": "Perfume + Body Mist"},
         ["Elegant Packaging", "Good Value", "Pleasant Fragrance"],
         ["Expensive", "Small Sizes", "Scent Clash"]),
        (engage, gift_sets, womens_gift_set, "Women's Gift Set", "Affordable perfume and deo combo", 899,
         {"contents": "Perfume + Deo"},
         ["Affordable", "Nice For Gifting", "Fresh Scents"],
         ["Cheap Packaging", "Weak Fragrance", "Small Quantities"]),
    ]
    _insert_products(category_id, rows)


# ---- Men's Grooming ------------------------------------------------------------------

def _seed_mens_grooming() -> None:
    category_id = nykaa_store.insert_category("Men's Grooming")

    beardo = nykaa_store.insert_brand("Beardo")
    ustraa = nykaa_store.insert_brand("Ustraa")
    man_company = nykaa_store.insert_brand("The Man Company")
    bombay_shaving = nykaa_store.insert_brand("Bombay Shaving Company")

    beard_care = nykaa_store.insert_subcategory(category_id, "Beard Care")
    face_care = nykaa_store.insert_subcategory(category_id, "Face Care")
    shaving = nykaa_store.insert_subcategory(category_id, "Shaving")
    hair_styling = nykaa_store.insert_subcategory(category_id, "Hair Styling")

    beard_oil = nykaa_store.insert_sub_subcategory(beard_care, "Beard Oil")
    beard_wash = nykaa_store.insert_sub_subcategory(beard_care, "Beard Wash")
    face_wash = nykaa_store.insert_sub_subcategory(face_care, "Face Wash")
    moisturizer = nykaa_store.insert_sub_subcategory(face_care, "Moisturizer")
    shaving_foam = nykaa_store.insert_sub_subcategory(shaving, "Shaving Foam")
    aftershave = nykaa_store.insert_sub_subcategory(shaving, "Aftershave")
    hair_wax = nykaa_store.insert_sub_subcategory(hair_styling, "Hair Wax")
    hair_gel = nykaa_store.insert_sub_subcategory(hair_styling, "Hair Gel")

    rows = [
        (beardo, beard_care, beard_oil, "Beard & Bhringraj Growth Oil", "Ayurvedic beard growth oil", 399,
         {"size": "30ml"},
         ["Promotes Growth", "Non-Greasy", "Nice Fragrance"],
         ["Expensive For Size", "Slow Results", "Strong Smell"]),
        (ustraa, beard_care, beard_oil, "Beard Growth Oil", "Nourishing beard growth oil", 449,
         {"size": "35ml"},
         ["Softens Beard", "Reduces Itchiness", "Lightweight"],
         ["Pricey", "Small Bottle", "Delayed Results"]),
        (man_company, beard_care, beard_wash, "Beard Wash", "Cleansing wash for beard hair", 349,
         {"size": "100ml"},
         ["Cleanses Well", "Nice Fragrance", "Softens Beard"],
         ["Expensive", "Drying", "Small Bottle"]),
        (bombay_shaving, beard_care, beard_wash, "Beard Wash", "Gentle daily beard wash", 299,
         {"size": "100ml"},
         ["Good Lather", "Fresh Scent", "Affordable"],
         ["Drying", "Weak Fragrance", "Runs Out Fast"]),
        (ustraa, face_care, face_wash, "De Tan Face Wash", "Tan-removal face wash for men", 249,
         {"skin_type": "Oily", "size": "100g"},
         ["Removes Tan", "Fresh Feel", "Affordable"],
         ["Drying", "Strong Fragrance", "Slow Results"]),
        (man_company, face_care, face_wash, "Charcoal Face Wash", "Deep-cleansing charcoal face wash", 299,
         {"skin_type": "Oily", "size": "100g"},
         ["Deep Cleansing", "Controls Oil", "Nice Fragrance"],
         ["Drying", "Expensive", "Small Tube"]),
        (beardo, face_care, moisturizer, "Oil Control Moisturizer", "Oil-control daily face moisturizer", 349,
         {"skin_type": "Oily", "size": "50g"},
         ["Non-Greasy", "Lightweight", "Fast Absorbing"],
         ["Mild Moisturization", "Expensive", "Strong Fragrance"]),
        (bombay_shaving, face_care, moisturizer, "Daily Face Moisturizer", "Lightweight daily face moisturizer", 399,
         {"skin_type": "Normal", "size": "50g"},
         ["Hydrating", "Lightweight", "Good Fragrance"],
         ["Pricey", "Greasy Feel", "Small Jar"]),
        (man_company, shaving, shaving_foam, "Shaving Foam", "Rich-lather shaving foam", 299,
         {"size": "200g"},
         ["Rich Lather", "Smooth Shave", "Nice Fragrance"],
         ["Expensive", "Drying", "Strong Smell"]),
        (ustraa, shaving, shaving_foam, "De-Tan Shaving Foam", "Smooth-glide shaving foam", 249,
         {"size": "200g"},
         ["Good Lather", "Smooth Glide", "Affordable"],
         ["Drying", "Weak Fragrance", "Foams Little"]),
        (bombay_shaving, shaving, aftershave, "Aftershave Lotion", "Soothing alcohol-based aftershave", 299,
         {"size": "100ml"},
         ["Soothing", "Fresh Scent", "Non-Sticky"],
         ["Stings Skin", "Strong Alcohol Smell", "Expensive"]),
        (beardo, shaving, aftershave, "Aftershave Splash", "Cooling aftershave splash", 349,
         {"size": "100ml"},
         ["Cooling Effect", "Nice Fragrance", "Long Lasting"],
         ["Stings", "Expensive", "Strong Smell"]),
        (ustraa, hair_styling, hair_wax, "Hair Wax", "Strong-hold matte hair wax", 299,
         {"hold": "Strong", "finish": "Matte"},
         ["Strong Hold", "Matte Finish", "Easy To Style"],
         ["Hard To Wash Out", "Small Jar", "Sticky"]),
        (beardo, hair_styling, hair_wax, "Hair Wax", "Long-hold styling hair wax", 275,
         {"hold": "Strong", "finish": "Matte"},
         ["Long Hold", "Non-Greasy", "Affordable"],
         ["Stiff Texture", "Flakes", "Hard To Reapply"]),
        (man_company, hair_styling, hair_gel, "Hair Styling Gel", "Glossy-finish styling gel", 249,
         {"hold": "Medium", "finish": "Glossy"},
         ["Good Hold", "Shiny Finish", "Affordable"],
         ["Sticky", "Flakes Over Time", "Stiff Feel"]),
        (bombay_shaving, hair_styling, hair_gel, "Hair Gel", "Matte-finish styling gel", 225,
         {"hold": "Medium", "finish": "Matte"},
         ["Easy Application", "Non-Sticky", "Affordable"],
         ["Weak Hold", "Dries Out Hair", "Small Tube"]),
    ]
    _insert_products(category_id, rows)


# ---- Beauty Tools ------------------------------------------------------------------

def _seed_beauty_tools() -> None:
    category_id = nykaa_store.insert_category("Beauty Tools")

    vega = nykaa_store.insert_brand("Vega")
    gubb = nykaa_store.insert_brand("GUBB")
    bronson = nykaa_store.insert_brand("Bronson Professional")
    real_techniques = nykaa_store.insert_brand("Real Techniques")

    makeup_brushes = nykaa_store.insert_subcategory(category_id, "Makeup Brushes")
    hair_tools = nykaa_store.insert_subcategory(category_id, "Hair Styling Tools")
    sponges = nykaa_store.insert_subcategory(category_id, "Beauty Sponges")
    grooming_tools = nykaa_store.insert_subcategory(category_id, "Grooming Tools")

    face_brush = nykaa_store.insert_sub_subcategory(makeup_brushes, "Face Brush")
    eye_brush = nykaa_store.insert_sub_subcategory(makeup_brushes, "Eye Brush")
    hair_dryer = nykaa_store.insert_sub_subcategory(hair_tools, "Hair Dryer")
    hair_straightener = nykaa_store.insert_sub_subcategory(hair_tools, "Hair Straightener")
    makeup_sponge = nykaa_store.insert_sub_subcategory(sponges, "Makeup Sponge")
    blender_puff = nykaa_store.insert_sub_subcategory(sponges, "Blender Puff")
    eyelash_curler = nykaa_store.insert_sub_subcategory(grooming_tools, "Eyelash Curler")
    tweezers = nykaa_store.insert_sub_subcategory(grooming_tools, "Tweezers")

    rows = [
        (real_techniques, makeup_brushes, face_brush, "Miracle Face Brush", "Dome-shaped foundation blending brush", 899,
         {"material": "Synthetic Bristle"},
         ["Flawless Blending", "Soft Bristles", "Durable"],
         ["Expensive", "Sheds Bristles", "Hard To Clean"]),
        (vega, makeup_brushes, face_brush, "Professional Face Brush Set", "5-piece face makeup brush set", 599,
         {"material": "Synthetic Bristle", "pieces": "5"},
         ["Good Value", "Soft Bristles", "Complete Set"],
         ["Sheds A Little", "Flimsy Handles", "Cheap Casing"]),
        (gubb, makeup_brushes, eye_brush, "Eye Makeup Brush Set", "6-piece precision eye brush set", 349,
         {"material": "Synthetic Bristle", "pieces": "6"},
         ["Affordable", "Precise Application", "Compact Set"],
         ["Sheds Bristles", "Flimsy Build", "Small Handles"]),
        (bronson, makeup_brushes, eye_brush, "Eye Brush Kit", "7-piece eye makeup brush kit", 399,
         {"material": "Synthetic Bristle", "pieces": "7"},
         ["Good Precision", "Value For Money", "Soft Bristles"],
         ["Cheap Packaging", "Sheds A Bit", "Loose Bristles"]),
        (vega, hair_tools, hair_dryer, "Compact Hair Dryer", "Compact fast-drying hair dryer", 899,
         {"wattage": "1000W"},
         ["Compact Size", "Lightweight", "Fast Drying"],
         ["Overheats", "Loud Noise", "Weak Airflow"]),
        (bronson, hair_tools, hair_dryer, "Professional Hair Dryer", "High-power salon-style hair dryer", 1499,
         {"wattage": "1800W"},
         ["Powerful Airflow", "Fast Drying", "Sturdy Build"],
         ["Heavy", "Overheats", "Loud"]),
        (gubb, hair_tools, hair_straightener, "Ceramic Hair Straightener", "Ceramic-plate hair straightener", 899,
         {"plate_material": "Ceramic"},
         ["Smooth Glide", "Even Heating", "Affordable"],
         ["Overheats", "Damages Hair", "Stopped Working"]),
        (vega, hair_tools, hair_straightener, "Professional Hair Straightener", "Fast heat-up ceramic straightener", 1199,
         {"plate_material": "Ceramic"},
         ["Fast Heat-Up", "Sleek Design", "Even Styling"],
         ["Expensive", "Heavy", "Cord Too Short"]),
        (real_techniques, sponges, makeup_sponge, "Miracle Complexion Sponge", "Latex-free makeup blending sponge", 649,
         {"material": "Latex-Free Foam"},
         ["Flawless Blending", "Soft Texture", "Doesn't Absorb Much Product"],
         ["Expensive", "Tears Easily", "Hard To Clean"]),
        (gubb, sponges, makeup_sponge, "Makeup Blending Sponge", "Multi-use makeup blending sponge", 199,
         {"material": "Latex-Free Foam"},
         ["Affordable", "Good Blending", "Soft Texture"],
         ["Absorbs Too Much Product", "Tears Easily", "Stains Over Time"]),
        (vega, sponges, blender_puff, "Beauty Blender Puff", "Teardrop-shaped foundation puff", 249,
         {"material": "Foam", "shape": "Teardrop"},
         ["Smooth Application", "Affordable", "Soft Texture"],
         ["Wears Out Fast", "Absorbs Product", "Stains"]),
        (bronson, sponges, blender_puff, "Blender Puff Set", "3-piece makeup blending puff set", 299,
         {"material": "Foam", "pieces": "3"},
         ["Good Value", "Soft Texture", "Even Blending"],
         ["Tears Easily", "Absorbs Product", "Cheap Material"]),
        (gubb, grooming_tools, eyelash_curler, "Eyelash Curler", "Stainless steel eyelash curler", 199,
         {"material": "Stainless Steel"},
         ["Curls Well", "Sturdy Build", "Affordable"],
         ["Pinches Eyelid", "Flimsy Spring", "Rubber Wears Out"]),
        (vega, grooming_tools, eyelash_curler, "Eyelash Curler", "Ergonomic-grip eyelash curler", 249,
         {"material": "Stainless Steel"},
         ["Comfortable Grip", "Good Curl Hold", "Durable"],
         ["Pinches Skin", "Spring Loosens", "Small Pad"]),
        (bronson, grooming_tools, tweezers, "Slant Tip Tweezers", "Slant-tip stainless steel tweezers", 149,
         {"material": "Stainless Steel", "tip": "Slanted"},
         ["Precise Grip", "Durable", "Affordable"],
         ["Tips Misalign", "Flimsy Build", "Loses Grip Over Time"]),
        (real_techniques, grooming_tools, tweezers, "Precision Tweezers", "Pointed-tip precision tweezers", 599,
         {"material": "Stainless Steel", "tip": "Pointed"},
         ["Sturdy Build", "Precise Tips", "Comfortable Grip"],
         ["Expensive", "Tips Bend", "Overpriced For Function"]),
    ]
    _insert_products(category_id, rows)


# ---- Wellness ------------------------------------------------------------------

def _seed_wellness() -> None:
    category_id = nykaa_store.insert_category("Wellness")

    hk_vitals = nykaa_store.insert_brand("HK Vitals")
    carbamide_forte = nykaa_store.insert_brand("Carbamide Forte")
    wellbeing_nutrition = nykaa_store.insert_brand("Wellbeing Nutrition")
    oziva = nykaa_store.insert_brand("OZiva")

    vitamins = nykaa_store.insert_subcategory(category_id, "Vitamins")
    protein = nykaa_store.insert_subcategory(category_id, "Protein")
    herbal_supplements = nykaa_store.insert_subcategory(category_id, "Herbal Supplements")
    gummies = nykaa_store.insert_subcategory(category_id, "Gummies")

    multivitamin = nykaa_store.insert_sub_subcategory(vitamins, "Multivitamin")
    vitamin_d = nykaa_store.insert_sub_subcategory(vitamins, "Vitamin D")
    whey_protein = nykaa_store.insert_sub_subcategory(protein, "Whey Protein")
    plant_protein = nykaa_store.insert_sub_subcategory(protein, "Plant Protein")
    ashwagandha = nykaa_store.insert_sub_subcategory(herbal_supplements, "Ashwagandha")
    omega_3 = nykaa_store.insert_sub_subcategory(herbal_supplements, "Omega-3")
    hair_gummies = nykaa_store.insert_sub_subcategory(gummies, "Hair Gummies")
    immunity_gummies = nykaa_store.insert_sub_subcategory(gummies, "Immunity Gummies")

    rows = [
        (hk_vitals, vitamins, multivitamin, "Multivitamin for Men", "Daily multivitamin for men's health", 499,
         {"count": "60 tablets", "flavor": "Unflavored"},
         ["Boosts Energy", "Good Value", "Easy To Swallow"],
         ["Large Tablets", "Delayed Effect", "Upset Stomach"]),
        (carbamide_forte, vitamins, multivitamin, "Multivitamin", "Complete daily multivitamin tablets", 399,
         {"count": "60 tablets", "flavor": "Unflavored"},
         ["Affordable", "Complete Nutrition", "Easy To Swallow"],
         ["Bad Aftertaste", "Slow Results", "Large Pills"]),
        (hk_vitals, vitamins, vitamin_d, "Vitamin D3", "Vitamin D3 supplement for bone health", 349,
         {"count": "60 capsules", "flavor": "Unflavored"},
         ["Improves Energy", "Good Value", "Easy To Take"],
         ["Delayed Effect", "Large Capsules", "Needs Long-Term Use"]),
        (oziva, vitamins, vitamin_d, "Vitamin D3+K2", "Plant-based Vitamin D3+K2 supplement", 499,
         {"count": "60 tablets", "flavor": "Unflavored"},
         ["Plant-Based", "Good Absorption", "Trusted Brand"],
         ["Expensive", "Slow Results", "Bitter Taste"]),
        (hk_vitals, protein, whey_protein, "Whey Protein", "Whey protein for muscle recovery", 1299,
         {"count": "1kg", "flavor": "Chocolate"},
         ["Good Taste", "Mixes Well", "Value For Money"],
         ["Bloating", "Chalky Texture", "Artificial Sweetener Taste"]),
        (oziva, protein, whey_protein, "Protein & Herbs Whey", "Herb-infused whey protein blend", 1599,
         {"count": "1kg", "flavor": "Chocolate"},
         ["Clean Ingredients", "Good Taste", "Digests Easily"],
         ["Expensive", "Doesn't Mix Well", "Small Quantity For Price"]),
        (oziva, protein, plant_protein, "Plant Protein", "Vegan plant-based protein powder", 1799,
         {"count": "1kg", "flavor": "Chocolate"},
         ["Vegan Friendly", "Easy Digestion", "Good Taste"],
         ["Expensive", "Grainy Texture", "Weak Flavor"]),
        (wellbeing_nutrition, protein, plant_protein, "Plant Protein Isolate", "Clean-label plant protein isolate", 1699,
         {"count": "500g", "flavor": "Vanilla"},
         ["Clean Label", "Digests Well", "Good Taste"],
         ["Expensive", "Small Pack", "Chalky Aftertaste"]),
        (carbamide_forte, herbal_supplements, ashwagandha, "Ashwagandha", "Ashwagandha capsules for stress relief", 399,
         {"count": "60 capsules", "flavor": "Unflavored"},
         ["Reduces Stress", "Improves Sleep", "Affordable"],
         ["Delayed Effect", "Large Capsules", "Mild Drowsiness"]),
        (hk_vitals, herbal_supplements, ashwagandha, "Ashwagandha", "Daily ashwagandha stress-relief capsules", 349,
         {"count": "60 capsules", "flavor": "Unflavored"},
         ["Calming Effect", "Good Value", "Easy To Take"],
         ["Slow Results", "Bitter Smell", "Needs Consistency"]),
        (wellbeing_nutrition, herbal_supplements, omega_3, "Omega-3", "Omega-3 fish oil softgels", 899,
         {"count": "60 softgels", "flavor": "Lemon"},
         ["No Fishy Aftertaste", "Good Quality", "Easy To Swallow"],
         ["Expensive", "Large Softgels", "Slow Results"]),
        (carbamide_forte, herbal_supplements, omega_3, "Omega-3 Fish Oil", "Affordable omega-3 fish oil capsules", 499,
         {"count": "60 softgels", "flavor": "Unflavored"},
         ["Affordable", "Good Value", "Easy To Take"],
         ["Fishy Burps", "Large Capsules", "Delayed Effect"]),
        (wellbeing_nutrition, gummies, hair_gummies, "Hair Gummies", "Biotin-based hair growth gummies", 699,
         {"count": "60 gummies", "flavor": "Mixed Berry"},
         ["Tasty", "Easy To Take", "Reduces Hairfall"],
         ["Expensive", "Slow Results", "Sugar Content"]),
        (oziva, gummies, hair_gummies, "Hair Gummies", "Vitamin-enriched hair gummies", 799,
         {"count": "60 gummies", "flavor": "Orange"},
         ["Good Taste", "Convenient", "Visible Results Over Time"],
         ["Pricey", "Sticky Texture", "Delayed Effect"]),
        (hk_vitals, gummies, immunity_gummies, "Immunity Gummies", "Daily immunity-boosting gummies", 449,
         {"count": "60 gummies", "flavor": "Orange"},
         ["Tasty", "Boosts Immunity", "Easy For Kids"],
         ["Sugar Content", "Expensive", "Mild Effect"]),
        (carbamide_forte, gummies, immunity_gummies, "Immunity Gummies", "Vitamin C immunity gummies", 399,
         {"count": "60 gummies", "flavor": "Mixed Fruit"},
         ["Good Taste", "Affordable", "Convenient"],
         ["Sticky Gummies", "Slow Results", "Sugar Heavy"]),
    ]
    _insert_products(category_id, rows)


# ---- Personal Care ------------------------------------------------------------------

def _seed_personal_care() -> None:
    category_id = nykaa_store.insert_category("Personal Care")

    dove = nykaa_store.insert_brand("Dove")
    nivea = nykaa_store.insert_brand("NIVEA")
    dettol = nykaa_store.insert_brand("Dettol")
    himalaya = nykaa_store.insert_brand("Himalaya")

    oral_care = nykaa_store.insert_subcategory(category_id, "Oral Care")
    feminine_hygiene = nykaa_store.insert_subcategory(category_id, "Feminine Hygiene")
    deodorants = nykaa_store.insert_subcategory(category_id, "Deodorants")
    intimate_care = nykaa_store.insert_subcategory(category_id, "Intimate Care")

    toothpaste = nykaa_store.insert_sub_subcategory(oral_care, "Toothpaste")
    mouthwash = nykaa_store.insert_sub_subcategory(oral_care, "Mouthwash")
    sanitary_pads = nykaa_store.insert_sub_subcategory(feminine_hygiene, "Sanitary Pads")
    menstrual_cups = nykaa_store.insert_sub_subcategory(feminine_hygiene, "Menstrual Cups")
    roll_on = nykaa_store.insert_sub_subcategory(deodorants, "Roll-On")
    spray = nykaa_store.insert_sub_subcategory(deodorants, "Spray")
    intimate_wash = nykaa_store.insert_sub_subcategory(intimate_care, "Intimate Wash")
    wipes = nykaa_store.insert_sub_subcategory(intimate_care, "Wipes")

    rows = [
        (himalaya, oral_care, toothpaste, "Complete Care Toothpaste", "Herbal daily-care toothpaste", 99,
         {"size": "150g"},
         ["Fresh Breath", "Herbal Ingredients", "Affordable"],
         ["Weak Foaming", "Mild Taste", "Tube Splits"]),
        (dettol, oral_care, toothpaste, "Fresh Toothpaste", "Germ-protection daily toothpaste", 89,
         {"size": "150g"},
         ["Fights Germs", "Fresh Feel", "Affordable"],
         ["Medicinal Taste", "Weak Foaming", "Strong Smell"]),
        (dettol, oral_care, mouthwash, "Fresh Mouthwash", "Germ-kill antiseptic mouthwash", 149,
         {"size": "250ml"},
         ["Kills Germs", "Long Freshness", "Affordable"],
         ["Strong Taste", "Burning Sensation", "Medicinal Smell"]),
        (himalaya, oral_care, mouthwash, "Herbal Mouthwash", "Natural herbal mouthwash", 129,
         {"size": "215ml"},
         ["Natural Ingredients", "Mild Taste", "Fresh Breath"],
         ["Weak Effect", "Short Freshness", "Mild Burning"]),
        (dove, feminine_hygiene, sanitary_pads, "Cotton Soft Sanitary Pads", "Soft-cover daily sanitary pads", 179,
         {"count": "20 pads", "size": "Regular"},
         ["Soft Material", "Good Absorption", "Comfortable Fit"],
         ["Leaks At Night", "Rustling Sound", "Adhesive Issue"]),
        (nivea, feminine_hygiene, sanitary_pads, "Comfort Sanitary Pads", "Extra-coverage overnight sanitary pads", 165,
         {"count": "20 pads", "size": "XL"},
         ["Soft Material", "Good Coverage", "Affordable"],
         ["Leaks Sometimes", "Thick Feel", "Adhesive Weak"]),
        (nivea, feminine_hygiene, menstrual_cups, "Silicone Menstrual Cup", "Reusable medical-grade menstrual cup", 399,
         {"size": "Medium", "material": "Medical Silicone"},
         ["Eco-Friendly", "Reusable", "Comfortable Fit"],
         ["Hard To Insert", "Leaks Initially", "Learning Curve"]),
        (dove, feminine_hygiene, menstrual_cups, "Comfort Menstrual Cup", "Soft-fit reusable menstrual cup", 449,
         {"size": "Small", "material": "Medical Silicone"},
         ["Comfortable", "Long Wear Time", "Eco-Friendly"],
         ["Difficult Removal", "Leaks If Misplaced", "Needs Practice"]),
        (dove, deodorants, roll_on, "Roll-On Deodorant", "Gentle long-lasting roll-on deodorant", 175,
         {"size": "50ml"},
         ["Gentle Formula", "Long Lasting", "Pleasant Smell"],
         ["Sticky Feel", "Stains Clothes", "Mild Fragrance"]),
        (nivea, deodorants, roll_on, "Roll-On Deodorant", "Smooth-glide roll-on deodorant", 165,
         {"size": "50ml"},
         ["Smooth Application", "Long Lasting", "Affordable"],
         ["Leaves Residue", "Short Lasting", "Sticky"]),
        (nivea, deodorants, spray, "Deodorant Spray", "All-day fresh deodorant spray", 189,
         {"size": "150ml"},
         ["Good Fragrance", "Long Lasting", "Affordable"],
         ["Strong Spray", "Skin Irritation", "Overpowering"]),
        (dove, deodorants, spray, "Deodorant Spray", "Gentle-formula deodorant spray", 199,
         {"size": "150ml"},
         ["Fresh Fragrance", "Long Lasting", "Gentle Formula"],
         ["Overpowering", "Gas Pressure Issue", "Fades Fast"]),
        (dettol, intimate_care, intimate_wash, "Intimate Wash", "pH-balanced intimate hygiene wash", 199,
         {"size": "100ml"},
         ["Maintains pH Balance", "Gentle Formula", "Fresh Feel"],
         ["Expensive", "Strong Fragrance", "Mild Irritation"]),
        (himalaya, intimate_care, intimate_wash, "Intimate Wash", "Natural herbal intimate wash", 175,
         {"size": "100ml"},
         ["Natural Ingredients", "Gentle On Skin", "Fresh Feel"],
         ["Mild Effect", "Weak Fragrance", "Small Bottle"]),
        (himalaya, intimate_care, wipes, "Feminine Hygiene Wipes", "Gentle natural hygiene wipes", 129,
         {"count": "10 wipes"},
         ["Natural Ingredients", "Gentle On Skin", "Handy Pack"],
         ["Small Pack", "Dries Quickly", "Expensive Per Wipe"]),
        (dettol, intimate_care, wipes, "Intimate Hygiene Wipes", "Germ-protection intimate wipes", 149,
         {"count": "20 wipes"},
         ["Convenient", "Gentle Formula", "Travel Friendly"],
         ["Dries Out Fast", "Small Pack", "Fragrance Too Strong"]),
    ]
    _insert_products(category_id, rows)


# ---- Nail Care ------------------------------------------------------------------

def _seed_nail_care() -> None:
    category_id = nykaa_store.insert_category("Nail Care")

    lakme = nykaa_store.insert_brand("Lakmé")
    nykaa_cosmetics = nykaa_store.insert_brand("Nykaa Cosmetics")
    colorbar = nykaa_store.insert_brand("Colorbar")
    faces_canada = nykaa_store.insert_brand("Faces Canada")

    nail_polish = nykaa_store.insert_subcategory(category_id, "Nail Polish")
    nail_treatment = nykaa_store.insert_subcategory(category_id, "Nail Treatment")
    nail_art = nykaa_store.insert_subcategory(category_id, "Nail Art")
    nail_remover = nykaa_store.insert_subcategory(category_id, "Nail Remover")

    matte_nail_paint = nykaa_store.insert_sub_subcategory(nail_polish, "Matte Nail Paint")
    gel_nail_paint = nykaa_store.insert_sub_subcategory(nail_polish, "Gel Nail Paint")
    nail_strengthener = nykaa_store.insert_sub_subcategory(nail_treatment, "Nail Strengthener")
    cuticle_oil = nykaa_store.insert_sub_subcategory(nail_treatment, "Cuticle Oil")
    nail_stickers = nykaa_store.insert_sub_subcategory(nail_art, "Nail Stickers")
    nail_glitter = nykaa_store.insert_sub_subcategory(nail_art, "Nail Glitter")
    acetone_remover = nykaa_store.insert_sub_subcategory(nail_remover, "Acetone Remover")
    non_acetone_remover = nykaa_store.insert_sub_subcategory(nail_remover, "Non-Acetone Remover")

    rows = [
        (lakme, nail_polish, matte_nail_paint, "Matte Nail Paint", "Quick-dry matte nail polish", 149,
         {"shade": "Coral Crush", "finish": "Matte"},
         ["Rich Color", "Quick Drying", "Affordable"],
         ["Chips Easily", "Uneven Application", "Streaky"]),
        (colorbar, nail_polish, matte_nail_paint, "Velvet Matte Nail Paint", "Long-wear velvet matte nail polish", 299,
         {"shade": "Deep Red", "finish": "Matte"},
         ["Long Lasting", "Rich Pigment", "Smooth Application"],
         ["Expensive", "Chips Fast", "Thick Brush"]),
        (nykaa_cosmetics, nail_polish, gel_nail_paint, "Gel Nail Paint", "High-shine gel-finish nail polish", 349,
         {"shade": "Ruby Red", "finish": "Glossy"},
         ["Glossy Finish", "Long Lasting", "Good Pigment"],
         ["Expensive", "Chips Around Edges", "Streaky First Coat"]),
        (faces_canada, nail_polish, gel_nail_paint, "Ultime Pro Gel Nail Paint", "Salon-like gel nail polish", 299,
         {"shade": "Nude Pink", "finish": "Glossy"},
         ["Salon-Like Finish", "Quick Drying", "Good Color Payoff"],
         ["Chips Easily", "Needs Top Coat", "Small Bottle"]),
        (lakme, nail_treatment, nail_strengthener, "Nail Strengthener", "Nail-strengthening base coat treatment", 199,
         {"size": "9ml"},
         ["Strengthens Nails", "Prevents Breakage", "Affordable"],
         ["Slow Results", "Thick Consistency", "Small Bottle"]),
        (colorbar, nail_treatment, nail_strengthener, "Nail Strengthener", "Breakage-control nail strengthener", 249,
         {"size": "12ml"},
         ["Visible Results", "Good Coverage", "Smooth Application"],
         ["Expensive", "Sticky Texture", "Delayed Effect"]),
        (nykaa_cosmetics, nail_treatment, cuticle_oil, "Cuticle Oil", "Nourishing cuticle care oil", 299,
         {"size": "10ml"},
         ["Nourishes Cuticles", "Non-Greasy", "Pleasant Scent"],
         ["Expensive", "Small Bottle", "Slow Absorption"]),
        (faces_canada, nail_treatment, cuticle_oil, "Cuticle Care Oil", "Softening daily cuticle oil", 249,
         {"size": "10ml"},
         ["Softens Cuticles", "Lightweight", "Affordable"],
         ["Mild Effect", "Small Quantity", "Greasy Feel"]),
        (colorbar, nail_art, nail_stickers, "Nail Art Stickers", "Ready-to-apply nail art stickers", 149,
         {"count": "24 stickers"},
         ["Easy To Apply", "Fun Designs", "Affordable"],
         ["Peels Off Fast", "Doesn't Stick Well", "Limited Designs"]),
        (nykaa_cosmetics, nail_art, nail_stickers, "Nail Art Stickers", "Trendy design nail art stickers", 199,
         {"count": "20 stickers"},
         ["Trendy Designs", "Easy Application", "Good Quality"],
         ["Expensive", "Peels Quickly", "Small Sheet"]),
        (faces_canada, nail_art, nail_glitter, "Nail Glitter", "Sparkle-finish nail glitter", 149,
         {"shade": "Gold", "finish": "Glitter"},
         ["Sparkly Finish", "Easy To Use", "Affordable"],
         ["Messy Application", "Uneven Spread", "Hard To Remove"]),
        (lakme, nail_art, nail_glitter, "Nail Glitter", "Shimmer-finish nail glitter", 129,
         {"shade": "Silver", "finish": "Glitter"},
         ["Good Shine", "Affordable", "Fun Look"],
         ["Chunky Glitter", "Messy", "Hard To Remove"]),
        (lakme, nail_remover, acetone_remover, "Nail Color Remover", "Fast-acting acetone nail polish remover", 99,
         {"size": "27ml"},
         ["Removes Polish Fast", "Affordable", "Effective"],
         ["Strong Smell", "Drying", "Dries Out Nails"]),
        (colorbar, nail_remover, acetone_remover, "Acetone Nail Polish Remover", "Quick-action acetone remover", 129,
         {"size": "100ml"},
         ["Fast Acting", "Good Value", "Effective On Gel"],
         ["Strong Fumes", "Very Drying", "Whitens Nails"]),
        (nykaa_cosmetics, nail_remover, non_acetone_remover, "Non-Acetone Remover", "Gentle non-acetone polish remover", 199,
         {"size": "100ml"},
         ["Gentle On Nails", "Mild Fragrance", "Non-Drying"],
         ["Slow To Remove Polish", "Expensive", "Needs More Product"]),
        (faces_canada, nail_remover, non_acetone_remover, "Gentle Nail Remover", "Nourishing non-acetone nail remover", 175,
         {"size": "100ml"},
         ["Gentle Formula", "Nourishing", "Mild Smell"],
         ["Takes Longer To Work", "Expensive For Size", "Weak On Gel Polish"]),
    ]
    _insert_products(category_id, rows)

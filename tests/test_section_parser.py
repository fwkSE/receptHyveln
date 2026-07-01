"""Tests for generic section-based HTML recipe parsing."""

from app.extractor import extract_recipe
from app.section_parser import parse_recipe_from_sections, parse_section_ingredient_groups

NIIINIS_HTML = """
<html><body><article class="post">
<h1>Spicy Kycklingwok</h1>
<h2>SPICY KYCKLINGWOK, 4 port</h2>
<p class="wp-block-paragraph"><strong>INGREDIENSER: </strong></p>
<p class="wp-block-paragraph">800 g kycklinginnerfileer</p>
<p class="wp-block-paragraph">1 1/2 röd paprika</p>
<p class="wp-block-paragraph">1 knippe salladslök</p>
<p class="wp-block-paragraph">1 tsk chiliflakes</p>
<p class="wp-block-paragraph">Gör såhär:</p>
<p class="wp-block-paragraph">1. Strimla kycklinginnerfileerna i mindre bitar.</p>
<p class="wp-block-paragraph">2. Strimla paprika och salladslök.</p>
<p class="wp-block-paragraph">Hittar du inte Chili Lime kryddan kan du göra en egen:</p>
<p class="wp-block-paragraph">1 msk chilipulver</p>
<p class="wp-block-paragraph">3. Häll i fisksås och sesamolja.</p>
<p class="wp-block-paragraph">4. Koka nudlar under tiden.</p>
<h2>Mer med kyckling:</h2>
</article></body></html>
"""

GENERIC_LIST_HTML = """
<html><body><article>
<h1>Pannkakor</h1>
<h2>Ingredienser</h2>
<ul>
  <li>2 dl vetemjöl</li>
  <li>3 dl mjölk</li>
  <li>2 ägg</li>
</ul>
<h2>Gör så här</h2>
<ol>
  <li>1. Blanda mjöl och mjölk.</li>
  <li>2. Stek pannkakorna.</li>
</ol>
</article></body></html>
"""


def test_parse_section_ingredient_groups_from_wordpress_blocks():
    groups = parse_section_ingredient_groups(NIIINIS_HTML)
    assert groups is not None
    assert len(groups[0]["ingredients"]) == 4
    assert groups[0]["ingredients"][0] == "800 g kycklinginnerfileer"


def test_parse_recipe_from_sections_wordpress():
    result = parse_recipe_from_sections(NIIINIS_HTML)
    assert result is not None
    assert result["title"] == "Spicy Kycklingwok"
    assert result["yield"] == "4 portioner"
    assert len(result["ingredients"]) == 4
    assert len(result["steps"]) == 4
    assert result["steps"][0].startswith("Strimla kyckling")
    assert "chilipulver" not in " ".join(result["steps"])


def test_parse_recipe_from_sections_list_markup():
    result = parse_recipe_from_sections(GENERIC_LIST_HTML)
    assert result is not None
    assert result["title"] == "Pannkakor"
    assert result["ingredients"] == ["2 dl vetemjöl", "3 dl mjölk", "2 ägg"]
    assert len(result["steps"]) == 2


ARTICLE_ONLY_HTML = """
<html><body><article>
<script type="application/ld+json">{"@type":"Article","headline":"Spicy Kycklingwok"}</script>
<h1>Spicy Kycklingwok</h1>
<h2>SPICY KYCKLINGWOK, 4 port</h2>
<p><strong>INGREDIENSER:</strong></p>
<p>800 g kycklinginnerfileer</p>
<p>1 tsk chiliflakes</p>
<p>2 tsk sesamolja</p>
<p>Gör såhär:</p>
<p>1. Stek kycklingen.</p>
<p>2. Tillsätt sås.</p>
</article></body></html>
"""


def test_extract_recipe_falls_back_to_sections_without_recipe_schema():
    result = extract_recipe(ARTICLE_ONLY_HTML, "https://www.niiinis.se/spicy-kycklingwok/")
    assert result["title"] == "Spicy Kycklingwok"
    assert len(result["ingredients"]) == 3
    assert len(result["steps"]) == 2


def test_parse_recipe_from_sections_rejects_blog_without_recipe():
    html = "<html><body><article><h1>Hej</h1><p>Bara text.</p></article></body></html>"
    assert parse_recipe_from_sections(html) is None


DU_BEHOVER_HTML = """
<html><body><article>
<h1>Kycklinggryta</h1>
<h3>Du behöver</h3>
<ul>
  <li>500 g kyckling</li>
  <li>2 dl grädde</li>
  <li>1 lök</li>
</ul>
<h3>Så här gör du</h3>
<ol>
  <li>1. Bryn kycklingen.</li>
  <li>2. Tillsätt grädde.</li>
</ol>
</article></body></html>
"""


def test_parse_recipe_from_sections_du_behover_heading():
    result = parse_recipe_from_sections(DU_BEHOVER_HTML)
    assert result is not None
    assert result["ingredients"] == ["500 g kyckling", "2 dl grädde", "1 lök"]
    assert len(result["steps"]) == 2


BR_INGREDIENTS_HTML = """
<html><body><article>
<h1>Fläskytterfilé</h1>
<h2>Ingredienser</h2>
<p class="ingredient">
  500 g fläskytterfilé<br/>
  salt och peppar<br/>
  2 salladslökar<br/>
  1 lime
</p>
<h2>Gör så här</h2>
<p>1. Stek köttet.</p>
<p>2. Servera med lime.</p>
</article></body></html>
"""


def test_parse_recipe_from_sections_br_separated_ingredients():
    result = parse_recipe_from_sections(BR_INGREDIENTS_HTML)
    assert result is not None
    assert result["ingredients"] == [
        "500 g fläskytterfilé",
        "salt och peppar",
        "2 salladslökar",
        "1 lime",
    ]


SCORING_HTML = """
<html><body><article>
<h1>Rätt recept</h1>
<h2>Populära recept</h2>
<ul><li>Missa inte: annan rätt</li><li>Mer inspiration</li></ul>
<h2>Ingredienser</h2>
<p>2 dl mjöl</p>
<p>3 dl mjölk</p>
<p>2 ägg</p>
<h2>Gör så här</h2>
<p>1. Blanda allt.</p>
<p>2. Stek pannkakor.</p>
<h2>Mer mat</h2>
<p>1. Det här är inte ett steg.</p>
</article></body></html>
"""


def test_scoring_prefers_real_recipe_section():
    result = parse_recipe_from_sections(SCORING_HTML)
    assert result is not None
    assert result["ingredients"] == ["2 dl mjöl", "3 dl mjölk", "2 ägg"]
    assert result["steps"] == ["Blanda allt.", "Stek pannkakor."]


RECEPTEN_STYLE_HTML = """
<html><body><main>
<h1>Pannkakor</h1>
<h2>Ingredienser:</h2>
<ul class="list ingredients">
  <li>2,5 dl vetemjöl</li>
  <li>0,5 tsk salt</li>
  <li>6 dl mjölk</li>
</ul>
<h2>Utrustning:</h2>
<ul><li>stekpanna</li></ul>
<div class="sidebarWideTop step-by-step-title">
  <h2>Tillaga pannkaka så här:</h2>
</div>
<div>
  <ol>
    <li><p>Mät upp vetemjöl och salt i en bunke. Blanda.</p></li>
    <li><p>Tillsätt hälften av mjölken och vispa till en jämn smet.</p></li>
    <li><p>Vispa i äggen.</p></li>
  </ol>
</div>
</main></body></html>
"""


def test_parse_recipe_from_sections_recepten_style_layout():
    result = parse_recipe_from_sections(RECEPTEN_STYLE_HTML)
    assert result is not None
    assert result["title"] == "Pannkakor"
    assert result["ingredients"] == ["2,5 dl vetemjöl", "0,5 tsk salt", "6 dl mjölk"]
    assert "stekpanna" not in result["ingredients"]
    assert len(result["steps"]) == 3
    assert result["steps"][0].startswith("Mät upp vetemjöl")


VIVAVINOMAT_STYLE_HTML = """
<html><body><section class="content">
<h1>Grundrecept på pannkakor</h1>
<div class="recipe">
  <div class="recipe__list">
    <h2>Ingredienser</h2>
    <p>4 ägg<br/>4 dl vetemjöl<br/>8 dl mjölk<br/>1 tsk salt<br/>3 msk smält smör</p>
    <p><em>Smör till stekning</em></p>
  </div>
  <p class="recipe-step"><span>1.</span> Knäck äggen och vispa samman med mjölken.</p>
  <p class="recipe-step"><span>2.</span> Vispa ner mjölet, lite i taget.</p>
  <p class="recipe-step"><span>3.</span> Stek tunna pannkakor i lite smör.</p>
</div>
<article class="grid__post grid__post--assortment">
  <h1>Black Tower Fruity White BIB</h1>
</article>
</section></body></html>
"""


def test_parse_recipe_from_sections_vivavinomat_style_layout():
    result = parse_recipe_from_sections(VIVAVINOMAT_STYLE_HTML)
    assert result is not None
    assert result["title"] == "Grundrecept på pannkakor"
    assert result["ingredients"][:3] == ["4 ägg", "4 dl vetemjöl", "8 dl mjölk"]
    assert "Smör till stekning" in result["ingredients"]
    assert len(result["steps"]) == 3
    assert result["steps"][0].startswith("Knäck äggen")


def test_extract_recipe_vivavinomat_style_without_schema_ingredients():
    result = extract_recipe(
        VIVAVINOMAT_STYLE_HTML,
        "https://vivavinomat.se/recept/grundrecept-pa-pannkakor/",
    )
    assert result["ingredients"][:2] == ["4 ägg", "4 dl vetemjöl"]
    assert len(result["steps"]) == 3


MYKITCHENSTORIES_STYLE_HTML = """
<html><body>
<article class="elementor-grid-item ecs-post-loop">
  <h1>Relaterat recept</h1>
</article>
<div class="elementor elementor-location-single">
  <h1>Klassiska pannkakor</h1>
  <p>Ingredienser</p>
  <p>5 dl vetemjöl<br/>1 tsk salt<br/>12 dl mjölk<br/>6 ägg</p>
  <span class="eael-accordion-tab-title">Såhär gör du:</span>
  <p>Receptet ger 24 stycken klassiska pannkakor.</p>
  <ol>
    <li>Blanda ihop vetemjöl och salt i en bunke.</li>
    <li>Blanda ner resten av mjölken lite i taget.</li>
    <li>Stek tunna pannkakor i lite smör.</li>
  </ol>
</div>
</body></html>
"""


def test_parse_recipe_from_sections_mykitchenstories_elementor_layout():
    result = parse_recipe_from_sections(MYKITCHENSTORIES_STYLE_HTML)
    assert result is not None
    assert result["title"] == "Klassiska pannkakor"
    assert result["ingredients"][:2] == ["5 dl vetemjöl", "1 tsk salt"]
    assert len(result["steps"]) == 3
    assert result["steps"][0].startswith("Blanda ihop")


SWEDISH_SPOON_STYLE_HTML = """
<html><body>
<div class="et_pb_post_content">
  <h1>Rårakor</h1>
  <h2><strong>Så gör du rårakor</strong></h2>
  <p>Intro text that should not become an ingredient line.</p>
  <p>Du behöver verkligen inte ett recept för det här. Men, här kommer ett.</p>
  <p>2-3 mellanstora fasta potatisar per person (till huvudrätt)<br/>
  smör, att steka i<br/>
  salt och peppar</p>
  <ol>
    <li>Skala och riv potatisarna grovt.</li>
    <li>Blanda potatisen med salt och peppar.</li>
    <li>Servera omedelbart.</li>
  </ol>
</div>
</body></html>
"""


def test_parse_recipe_from_sections_swedish_spoon_prose_layout():
    result = parse_recipe_from_sections(SWEDISH_SPOON_STYLE_HTML)
    assert result is not None
    assert result["title"] == "Rårakor"
    assert result["ingredients"] == [
        "2-3 mellanstora fasta potatisar per person (till huvudrätt)",
        "smör, att steka i",
        "salt och peppar",
    ]
    assert len(result["steps"]) == 3
    assert result["steps"][0].startswith("Skala och riv")

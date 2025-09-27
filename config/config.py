import os
from dataclasses import dataclass, field
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class Config:
    """Production-ready configuration for Houzz Lead Generation Pipeline"""
    
    # ============================================================================
    # API CONFIGURATION
    # ============================================================================
    
    # Email Verification API
    ZEROBOUNCE_API_KEY: Optional[str] = os.getenv('ZEROBOUNCE_API_KEY')
    
    # Google Custom Search API
    GOOGLE_SEARCH_API_KEY: Optional[str] = os.getenv('GOOGLE_SEARCH_API_KEY')
    GOOGLE_SEARCH_CX: Optional[str] = os.getenv('GOOGLE_SEARCH_CX')
    
    # Proxy Configuration (optional)
    PROXY_USERNAME: Optional[str] = os.getenv('PROXY_USERNAME')
    PROXY_PASSWORD: Optional[str] = os.getenv('PROXY_PASSWORD')
    
    # Webshare Proxy Settings
    WEBSHARE_API_KEY: Optional[str] = os.getenv('WEBSHARE_API_KEY')
    WEBSHARE_PROXY_LIST: Optional[str] = os.getenv('WEBSHARE_PROXY_LIST')
    USE_PROXY_ROTATION: bool = os.getenv('USE_PROXY_ROTATION', 'false').lower() in ('true', '1', 'yes')
    PROXY_ROTATION_INTERVAL: int = int(os.getenv('PROXY_ROTATION_INTERVAL', '10').strip('"'))
    
    # ============================================================================
    # HOUZZ SETTINGS
    # ============================================================================
    
    HOUZZ_BASE_URL: str = "https://www.houzz.com"
    HOUZZ_PROFESSIONALS_URL: str = "https://www.houzz.com/professionals"
    
    # ============================================================================
    # SCRAPING TARGETS
    # ============================================================================
    
    # US States for scraping
    US_STATES: List[str] = field(default_factory=lambda: [
        'alabama', 'alaska', 'arizona', 'arkansas', 'california', 'colorado',
        'connecticut', 'delaware', 'florida', 'georgia', 'hawaii', 'idaho',
        'illinois', 'indiana', 'iowa', 'kansas', 'kentucky', 'louisiana',
        'maine', 'maryland', 'massachusetts', 'michigan', 'minnesota',
        'mississippi', 'missouri', 'montana', 'nebraska', 'nevada',
        'new-hampshire', 'new-jersey', 'new-mexico', 'new-york',
        'north-carolina', 'north-dakota', 'ohio', 'oklahoma', 'oregon',
        'pennsylvania', 'rhode-island', 'south-carolina', 'south-dakota',
        'tennessee', 'texas', 'utah', 'vermont', 'virginia', 'washington',
        'west-virginia', 'wisconsin', 'wyoming'
    ])
    
    # Professional types to scrape
    PROFESSIONAL_TYPES: List[str] = field(default_factory=lambda: [
        'interior-designer', 'architect', 'general-contractor', 'design-build',
        'landscape-architect', 'kitchen-and-bath', 'home-builders'
    ])
    
    # Professional type URL parameters (t_xxxxx values)
    PROFESSIONAL_TYPE_PARAMS: dict = field(default_factory=lambda: {
        'interior-designer': 't_11785', 'architect': 't_11784', 
        'general-contractor': 't_11783', 'design-build': 't_11782',
        'landscape-architect': 't_11786', 'kitchen-and-bath': 't_11790',
        'home-builders': 't_11781'
    })
    
    # State to major cities with region IDs
    STATE_CITY_REGIONS: dict = field(default_factory=lambda: {
        'alabama': [('huntsville-al-us', 'r_4068590'), ('birmingham-al-us', 'r_4049979'), ('montgomery-al-us', 'r_4076784'), ('mobile-al-us', 'r_4076598'), ('tuscaloosa-al-us', 'r_4094455'), ('hoover-al-us', 'r_4067994'), ('selma-al-us', 'r_4089114'), ('auburn-al-us', 'r_4830796')],
        'alaska': [('anchorage-ak-us', 'r_5879400'), ('fairbanks-ak-us', 'r_5861897'), ('knik-fairview-ak-us', 'r_7262897'), ('wasilla-ak-us', 'r_5877641'), ('meadow-lakes-ak-us', 'r_5868651'), ('lakes-ak-us', 'r_7262905')],
        'arizona': [('phoenix-az-us', 'r_5308655'), ('ahwatukee-az-us', 'r_5552450'), ('tucson-az-us', 'r_5318313'), ('mesa-az-us', 'r_5304391'), ('chandler-az-us', 'r_5289282'), ('gilbert-az-us', 'r_5295903'), ('glendale-az-us', 'r_5295985'), ('scottsdale-az-us', 'r_5313457'), ('peoria-az-us', 'r_5308480'), ('tempe-az-us', 'r_5317058'), ('tempe-junction-az-us', 'r_5317071'), ('surprise-az-us', 'r_5316428'), ('san-tan-valley-az-us', 'r_7310164'), ('yuma-az-us', 'r_5322053'), ('goodyear-az-us', 'r_5296266'), ('buckeye-az-us', 'r_5287262'), ('flagstaff-az-us', 'r_5294810')],
        'arkansas': [('little-rock-ar-us', 'r_4119403'), ('fayetteville-ar-us', 'r_4110486'), ('fort-smith-ar-us', 'r_4111410'), ('springdale-ar-us', 'r_4132093'), ('ft-smith-ar-us', 'r_101182470'), ('jonesboro-ar-us', 'r_4116834'), ('rogers-ar-us', 'r_4128894'), ('north-little-rock-ar-us', 'r_4124112'), ('conway-ar-us', 'r_4106458'), ('bentonville-ar-us', 'r_4101260'), ('hot-springs-ar-us', 'r_4115412')],
        'california': [('los-angeles-county-ca-us', 'r_5368381'), ('los-angeles-ca-us', 'r_5368361'), ('brentwood-los-angeles-ca-us', 'r_101182514'), ('bel-air-ca-us', 'r_101182513'), ('hollywood-ca-us', 'r_101182515'), ('san-diego-county-ca-us', 'r_5391832'), ('orange-county-ca-us', 'r_5379524'), ('alameda-county-ca-us', 'r_5322745'), ('san-diego-ca-us', 'r_5391811'), ('university-city-ca-us', 'r_5404814'), ('san-jose-ca-us', 'r_5392171'), ('san-francisco-ca-us', 'r_5391959'), ('ventura-county-ca-us', 'r_5405889'), ('fresno-ca-us', 'r_5350937'), ('sacramento-ca-us', 'r_5389489'), ('modesto-ca-us', 'r_5373900'), ('stockton-ca-us', 'r_5399020'), ('salinas-ca-us', 'r_5391295')],
        'colorado': [('denver-co-us', 'r_5419384'), ('indian-creek-co-us', 'r_101182619'), ('colorado-springs-co-us', 'r_5417598'), ('aurora-co-us', 'r_5412347'), ('fort-collins-co-us', 'r_5577147'), ('lakewood-co-us', 'r_5427946'), ('thornton-co-us', 'r_5441492'), ('arvada-co-us', 'r_5412199'), ('westminster-co-us', 'r_5443910'), ('pueblo-co-us', 'r_5435464'), ('centennial-co-us', 'r_5416541'), ('greeley-co-us', 'r_5577592'), ('boulder-co-us', 'r_5574991'), ('highlands-ranch-co-us', 'r_5425043'), ('glenwood-springs-co-us', 'r_5423092')],
        'connecticut': [('bridgeport-ct-us', 'r_5282804'), ('stamford-ct-us', 'r_4843564'), ('new-haven-ct-us', 'r_4839366'), ('hartford-ct-us', 'r_4835797'), ('north-stamford-ct-us', 'r_4839745'), ('waterbury-ct-us', 'r_4845193'), ('norwalk-ct-us', 'r_4839822'), ('danbury-ct-us', 'r_4832353'), ('east-norwalk-ct-us', 'r_4833505'), ('new-britain-ct-us', 'r_4839292'), ('west-hartford-ct-us', 'r_4845411'), ('greenwich-ct-us', 'r_4835395'), ('fairfield-ct-us', 'r_4834157'), ('hamden-ct-us', 'r_4835654'), ('meriden-ct-us', 'r_4838524'), ('bristol-ct-us', 'r_5282835'), ('manchester-ct-us', 'r_4838174'), ('middletown-ct-us', 'r_4838633'), ('enfield-ct-us', 'r_4834040'), ('torrington-ct-us', 'r_4844309')],
        'delaware': [('wilmington-de-us', 'r_4145381'), ('centreville-de-us', 'r_7142120'), ('ashland-de-us', 'r_4141266'), ('swallow-hill-de-us', 'r_4144903'), ('dover-de-us', 'r_4142290'), ('newark-de-us', 'r_4143861'), ('middletown-de-us', 'r_4143637'), ('bear-de-us', 'r_4141363'), ('glasgow-de-us', 'r_4142683'), ('brookside-de-us', 'r_4141674'), ('hockessin-de-us', 'r_4142969'), ('smyrna-de-us', 'r_4144764'), ('pike-creek-valley-de-us', 'r_4144101'), ('milford-de-us', 'r_4143658'), ('claymont-de-us', 'r_4141974'), ('wilmington-manor-de-us', 'r_4145395'), ('north-star-de-us', 'r_4143897'), ('pike-creek-de-us', 'r_4144100'), ('georgetown-de-us', 'r_4142643'), ('millsboro-de-us', 'r_4143690')],
        'florida': [('palm-beach-county-fl-us', 'r_4167510'), ('jacksonville-fl-us', 'r_4160021'), ('st-johns-fl-us', 'r_101182682'), ('brevard-county-fl-us', 'r_4148826'), ('miami-fl-us', 'r_4164138'), ('tampa-fl-us', 'r_4174757'), ('orlando-fl-us', 'r_4167147'), ('ocala-fl-us', 'r_4166673'), ('gainesville-fl-us', 'r_4156404'), ('kissimmee-fl-us', 'r_4160983'), ('daytona-beach-fl-us', 'r_4152872')],
        'georgia': [('atlanta-ga-us', 'r_4180439'), ('buckhead-atlanta-ga-us', 'r_101182744'), ('columbus-ga-us', 'r_4188985'), ('augusta-ga-us', 'r_4180531'), ('macon-ga-us', 'r_4207400'), ('savannah-ga-us', 'r_4221552'), ('athens-ga-us', 'r_4180386'), ('vidalia-ga-us', 'r_4228425'), ('albany-ga-us', 'r_4179320'), ('lagrange-ga-us', 'r_101182753')],
        'hawaii': [('honolulu-hi-us', 'r_5856195'), ('pearl-city-hi-us', 'r_5852275'), ('kailua-hi-us', 'r_5847486'), ('waipahu-hi-us', 'r_5854686'), ('kāne‘ohe-hi-us', 'r_5848189'), ('kaneohe-hi-us', 'r_101182782'), ('kailua-kona-hi-us', 'r_101185997'), ('mililani-town-hi-us', 'r_5851030'), ('kahului-hi-us', 'r_5847411'), ('kapolei-hi-us', 'r_6957263'), ('kīhei-hi-us', 'r_5849297'), ('‘ewa-gentry-hi-us', 'r_5855070'), ('makakilo-hi-us', 'r_7262761'), ('wailuku-hi-us', 'r_5854496'), ('makakilo-city-hi-us', 'r_5850554'), ('hālawa-hi-us', 'r_5855319'), ('‘ewa-beach-hi-us', 'r_5855051'), ('ewa-beach-hi-us', 'r_101182786')],
        'idaho': [('boise-id-us', 'r_5586437'), ('meridian-id-us', 'r_5600685'), ('nampa-id-us', 'r_5601933'), ('idaho-falls-id-us', 'r_5596475'), ('caldwell-id-us', 'r_5587698'), ('coeur-d-alene-id-us', 'r_101182879'), ('pocatello-id-us', 'r_5604045'), ("coeur-d'alene-id-us", 'r_5589173'), ('twin-falls-id-us', 'r_5610810'), ('post-falls-id-us', 'r_5604353'), ('rexburg-id-us', 'r_5605242'), ('eagle-id-us', 'r_5591778')],
        'illinois': [('chicago-il-us', 'r_4887398'), ('aurora-il-us', 'r_4883817'), ('fox-valley-il-us', 'r_101182888'), ('joliet-il-us', 'r_4898015'), ('naperville-il-us', 'r_4903279'), ('rockford-il-us', 'r_4907959'), ('springfield-il-us', 'r_4250542'), ('elgin-il-us', 'r_4890864'), ('bloomington-il-us', 'r_4885164'), ('peoria-il-us', 'r_4905687'), ('champaign-il-us', 'r_4887158'), ('effingham-il-us', 'r_4237727')],
        'indiana': [('indianapolis-in-us', 'r_4259418'), ('fort-wayne-in-us', 'r_4920423'), ('ft-wayne-in-us', 'r_101182930'), ('evansville-in-us', 'r_4257227'), ('south-bend-in-us', 'r_4926563'), ('carmel-in-us', 'r_4255466'), ('fishers-in-us', 'r_4257494'), ('lafayette-in-us', 'r_4922462'), ('muncie-in-us', 'r_4924006'), ('bloomington-in-us', 'r_4254679'), ('richmond-in-us', 'r_4263681')],
        'iowa': [('des-moines-ia-us', 'r_4853828'), ('cedar-rapids-ia-us', 'r_4850751'), ('davenport-ia-us', 'r_4853423'), ('sioux-city-ia-us', 'r_4876523'), ('iowa-city-ia-us', 'r_4862034'), ('waterloo-ia-us', 'r_4880889'), ('west-des-moines-ia-us', 'r_4881346'), ('ankeny-ia-us', 'r_4846960'), ('ames-ia-us', 'r_4846834'), ('dubuque-ia-us', 'r_4854529'), ('urbandale-ia-us', 'r_4879890'), ('fort-dodge-ia-us', 'r_4857486'), ('mason-city-ia-us', 'r_4866445'), ('ottumwa-ia-us', 'r_4870380')],
        'kansas': [('wichita-ks-us', 'r_4281730'), ('overland-park-ks-us', 'r_4276873'), ('kansas-city-ks-us', 'r_4273837'), ('olathe-ks-us', 'r_4276614'), ('topeka-ks-us', 'r_4280539'), ('lawrence-ks-us', 'r_4274277'), ('shawnee-ks-us', 'r_4279247'), ('lenexa-ks-us', 'r_4274356'), ('manhattan-ks-us', 'r_4274994'), ('salina-ks-us', 'r_4278890'), ('hutchinson-ks-us', 'r_4273299'), ('leavenworth-ks-us', 'r_4274305'), ('great-bend-ks-us', 'r_4272340'), ('dodge-city-ks-us', 'r_5445298')],
        'kentucky': [('louisville-ky-us', 'r_4299276'), ('lexington-ky-us', 'r_4297983'), ('lexington-fayette-ky-us', 'r_4297999'), ('meads-ky-us', 'r_4300488'), ('owensboro-ky-us', 'r_4303436'), ('florence-ky-us', 'r_4291945'), ('elizabethtown-ky-us', 'r_4290988'), ('ashland-ky-us', 'r_4282757')],
        'louisiana': [('new-orleans-la-us', 'r_4335045'), ('orleans-parish-la-us', 'r_4336191'), ('baton-rouge-la-us', 'r_4315588'), ('shreveport-la-us', 'r_4341513'), ('metairie-terrace-la-us', 'r_4333190'), ('metairie-la-us', 'r_4333177'), ('alexandria-la-us', 'r_4314550'), ('lafayette-la-us', 'r_4330145'), ('deridder-la-us', 'r_4321781'), ('natchitoches-la-us', 'r_4334720')],
        'maine': [('portland-maine-me-us', 'r_4975802'), ('lewiston-me-us', 'r_4969398'), ('bangor-me-us', 'r_4957280'), ('west-scarborough-me-us', 'r_4982720'), ('south-portland-me-us', 'r_4979244'), ('south-portland-gardens-me-us', 'r_4979245'), ('auburn-me-us', 'r_4956976'), ('biddeford-me-us', 'r_4958141'), ('scarborough-me-us', 'r_4977882'), ('sanford-me-us', 'r_101183111'), ('augusta-me-us', 'r_4957003'), ('presque-isle-me-us', 'r_4975966')],
        'maryland': [('baltimore-md-us', 'r_4347778'), ('columbia-md-us', 'r_4352053'), ('germantown-md-us', 'r_4356050'), ('silver-spring-md-us', 'r_4369596'), ('southern-md-facility-md-us', 'r_101183100'), ('waldorf-md-us', 'r_4372599'), ('frederick-md-us', 'r_4355585'), ('ellicott-city-md-us', 'r_4354265'), ('glen-burnie-md-us', 'r_4356188'), ('annapolis-md-us', 'r_4347242'), ('gaithersburg-md-us', 'r_4355843'), ('westminster-md-us', 'r_4373238'), ('aberdeen-md-us', 'r_4346913')],
        'massachusetts': [('boston-ma-us', 'r_4930956'), ('cape-cod-ma-us', 'r_101183084'), ('barnstable-county-ma-us', 'r_4929772'), ('worcester-ma-us', 'r_4956184'), ('berkshire-ma-us', 'r_4930390'), ('springfield-ma-us', 'r_4951788'), ('cambridge-ma-us', 'r_4931972'), ('lowell-ma-us', 'r_4942618'), ('brockton-ma-us', 'r_4931429'), ('quincy-ma-us', 'r_4948247'), ('new-bedford-ma-us', 'r_4945121'), ('lynn-ma-us', 'r_4942807'), ('fall-river-ma-us', 'r_4936159'), ('newton-ma-us', 'r_4945283'), ('lawrence-ma-us', 'r_4941720'), ('gloucester-ma-us', 'r_4937829'), ('taunton-ma-us', 'r_4952629'), ('newburyport-ma-us', 'r_4945256'), ('leominster-ma-us', 'r_4941873')],
        'michigan': [('oakland-township-mi-us', 'r_101183198'), ('macomb-mi-us', 'r_5000473'), ('detroit-mi-us', 'r_4990729'), ('grand-rapids-mi-us', 'r_4994358'), ('warren-mi-us', 'r_5014051'), ('sterling-heights-mi-us', 'r_5011148'), ('ann-arbor-mi-us', 'r_4984247'), ('lansing-mi-us', 'r_4998830'), ('traverse-city-mi-us', 'r_5012495'), ('big-rapids-mi-us', 'r_4986020'), ('muskegon-mi-us', 'r_5003132'), ('saginaw-mi-us', 'r_5007989')],
        'minnesota': [('minneapolis-mn-us', 'r_5037649'), ('rochester-mn-us', 'r_5043473'), ('bloomington-mn-us', 'r_5018739'), ('duluth-mn-us', 'r_5024719'), ('brooklyn-park-mn-us', 'r_5019335'), ('plymouth-mn-us', 'r_5041926'), ('woodbury-mn-us', 'r_5053358'), ('maple-grove-mn-us', 'r_5036493'), ('lakeville-mn-us', 'r_5034059'), ('blaine-mn-us', 'r_5018651'), ('saint-cloud-mn-us', 'r_5044407'), ('eagan-mn-us', 'r_5024825'), ('brainerd-mn-us', 'r_5019116'), ('alexandria-mn-us', 'r_5016108'), ('grand-rapids-mn-us', 'r_5028537'), ('willmar-mn-us', 'r_5052916')],
        'mississippi': [('jackson-ms-us', 'r_4431410'), ('gulfport-ms-us', 'r_4428667'), ('west-gulfport-ms-us', 'r_4450687'), ('southaven-ms-us', 'r_4446675'), ('biloxi-ms-us', 'r_4418478'), ('hattiesburg-ms-us', 'r_4429295'), ('starkville-ms-us', 'r_4447161'), ('meridian-ms-us', 'r_4435764')],
        'missouri': [('kansas-city-mo-us', 'r_4393217'), ('city-of-saint-louis-mo-us', 'r_4407084'), ('st-louis-mo-us', 'r_4407066'), ('springfield-mo-us', 'r_4409896'), ('columbia-mo-us', 'r_4381982'), ('independence-mo-us', 'r_4391812'), ('east-independence-mo-us', 'r_4385018'), ('lees-summit-mo-us', 'r_101183223'), ('o-fallon-mo-us', 'r_101183225'), ("o'fallon-mo-us", 'r_4401242'), ('rolla-mo-us', 'r_4406282')],
        'montana': [('billings-mt-us', 'r_5640350'), ('missoula-mt-us', 'r_5666639'), ('great-falls-mt-us', 'r_5655240'), ('bozeman-mt-us', 'r_5641727'), ('butte-mt-us', 'r_5642934'), ('helena-mt-us', 'r_5656882'), ('kalispell-mt-us', 'r_5660340')],
        'nebraska': [('omaha-ne-us', 'r_5074472'), ('lincoln-ne-us', 'r_5072006'), ('bellevue-ne-us', 'r_5063805'), ('grand-island-ne-us', 'r_5069297'), ('kearney-ne-us', 'r_5071348'), ('fremont-ne-us', 'r_5068725'), ('hastings-ne-us', 'r_5069802'), ('papillion-ne-us', 'r_5074792'), ('north-platte-ne-us', 'r_5697939')],
        'nevada': [('las-vegas-nv-us', 'r_5506956'), ('henderson-nv-us', 'r_5505411'), ('reno-nv-us', 'r_5511077'), ('north-las-vegas-nv-us', 'r_5509403'), ('enterprise-nv-us', 'r_5503766'), ('spring-valley-nv-us', 'r_5512909'), ('sunrise-manor-nv-us', 'r_5513343'), ('paradise-nv-us', 'r_5509952'), ('sparks-nv-us', 'r_5512862'), ('carson-city-nv-us', 'r_5501344'), ('whitney-nv-us', 'r_5515110'), ('pahrump-nv-us', 'r_5509851'), ('winchester-nv-us', 'r_5515345'), ('summerlin-nv-us', 'r_101183444'), ('summerlin-south-nv-us', 'r_7262622'), ('sun-valley-nv-us', 'r_5513307'), ('fernley-nv-us', 'r_5504003')],
        'new-hampshire': [('manchester-nh-us', 'r_5089178'), ('nashua-nh-us', 'r_5090046'), ('concord-nh-us', 'r_5084868'), ('east-concord-nh-us', 'r_5085688'), ('derry-village-nh-us', 'r_5085382'), ('derry-nh-us', 'r_5085374'), ('dover-nh-us', 'r_5085520'), ('rochester-nh-us', 'r_5091872'), ('salem-nh-us', 'r_5092268'), ('merrimack-nh-us', 'r_5089478'), ('londonderry-nh-us', 'r_5088905'), ('hudson-nh-us', 'r_5087752'), ('bedford-nh-us', 'r_5083221'), ('keene-nh-us', 'r_5088262'), ('portsmouth-nh-us', 'r_5091383'), ('laconia-nh-us', 'r_5088438'), ('conway-nh-us', 'r_5084939'), ('lebanon-nh-us', 'r_5088597')],
        'new-jersey': [('new-jersey-us', 'r_5101760'), ('newark-nj-us', 'r_5101798'), ('jersey-city-nj-us', 'r_5099836'), ('paterson-nj-us', 'r_5102466'), ('elizabeth-nj-us', 'r_5097598'), ('lakewood-nj-us', 'r_5100280'), ('edison-nj-us', 'r_5097529'), ('trenton-nj-us', 'r_5105496'), ('toms-river-nj-us', 'r_4504476'), ('cherry-hill-nj-us', 'r_4501198'), ('hackettstown-nj-us', 'r_5098745')],
        'new-mexico': [('albuquerque-nm-us', 'r_5454711'), ('las-cruces-nm-us', 'r_5475352'), ('rio-rancho-nm-us', 'r_5487810'), ('enchanted-hills-nm-us', 'r_7839240'), ('santa-fe-nm-us', 'r_5490263'), ('roswell-nm-us', 'r_5488441'), ('farmington-nm-us', 'r_5467328'), ('south-valley-nm-us', 'r_5492450'), ('carlsbad-nm-us', 'r_5460459'), ('gallup-nm-us', 'r_5468773')],
        'new-york': [('new-york-us', 'r_5128638'), ('new-york-city-ny-us', 'r_5128581'), ('brooklyn-ny-us', 'r_5110302'), ('queens-ny-us', 'r_101183496'), ('borough-of-queens-ny-us', 'r_5133273'), ('manhattan-ny-us', 'r_5125771'), ('new-york-county-ny-us', 'r_5128594'), ('bronx-ny-us', 'r_101184817'), ('hempstead-ny-us', 'r_5120478'), ('staten-island-ny-us', 'r_5139568'), ('brookhaven-ny-us', 'r_5110292'), ('richmond-county-ny-us', 'r_5139559'), ('islip-ny-us', 'r_5122413'), ('oyster-bay-ny-us', 'r_5130327'), ('utica-ny-us', 'r_5142056'), ('syracuse-ny-us', 'r_5140405'), ('oneonta-ny-us', 'r_5129852'), ('ithaca-ny-us', 'r_5122432')],
        'north-carolina': [('charlotte-nc-us', 'r_4460243'), ('myers-park-nc-us', 'r_101183290'), ('raleigh-nc-us', 'r_4487042'), ('north-hills-nc-us', 'r_101183291'), ('greensboro-nc-us', 'r_4469146'), ('durham-nc-us', 'r_4464368'), ('winston-salem-nc-us', 'r_4499612'), ('fayetteville-nc-us', 'r_4466033'), ('cary-nc-us', 'r_4459467'), ('concord-nc-us', 'r_4461574')],
        'north-dakota': [('fargo-nd-us', 'r_5059163'), ('bismarck-nd-us', 'r_5688025'), ('grand-forks-nd-us', 'r_5059429'), ('minot-nd-us', 'r_5690532'), ('west-fargo-nd-us', 'r_5062458'), ('dickinson-nd-us', 'r_5688789'), ('mandan-nd-us', 'r_5690366'), ('jamestown-nd-us', 'r_5059836')],
        'ohio': [('columbus-oh-us', 'r_4509177'), ('hamilton-county-oh-us', 'r_4513583'), ('cleveland-oh-us', 'r_5150529'), ('cincinnati-oh-us', 'r_4508722'), ('toledo-oh-us', 'r_5174035'), ('akron-oh-us', 'r_5145476'), ('mansfield-oh-us', 'r_5161723'), ('chillicothe-oh-us', 'r_4828890'), ('dayton-oh-us', 'r_4509884')],
        'oklahoma': [('oklahoma-city-ok-us', 'r_4544349'), ('tulsa-ok-us', 'r_4553433'), ('norman-ok-us', 'r_4543762'), ('broken-arrow-ok-us', 'r_4531405'), ('edmond-ok-us', 'r_4535740'), ('moore-ok-us', 'r_4542975'), ('midwest-city-ok-us', 'r_4542765'), ('ardmore-ok-us', 'r_4529469'), ('mcalester-ok-us', 'r_4542367')],
        'oregon': [('portland-or-us', 'r_5746545'), ('salem-or-us', 'r_5750162'), ('eugene-or-us', 'r_5725846'), ('gresham-or-us', 'r_5729485'), ('hillsboro-or-us', 'r_5731371'), ('beaverton-or-us', 'r_5713376'), ('bend-or-us', 'r_5713587'), ('medford-or-us', 'r_5740099'), ('springfield-or-us', 'r_5754005'), ('la-grande-or-us', 'r_5735537')],
        'pennsylvania': [('southeastern-pa-us', 'r_101183591'), ('philadelphia-pa-us', 'r_4560349'), ('tinicum-township-pa-us', 'r_7259081'), ('pittsburgh-pa-us', 'r_5206379'), ('harrisburg-pa-us', 'r_5192726'), ('york-pa-us', 'r_4562407'), ('lancaster-pa-us', 'r_5197079'), ('chambersburg-pa-us', 'r_4557109')],
        'rhode-island': [('providence-ri-us', 'r_5224151'), ('warwick-ri-us', 'r_5225507'), ('cranston-ri-us', 'r_5221659'), ('city-of-cranston-ri-us', 'r_5221674'), ('pawtucket-ri-us', 'r_5223869'), ('east-providence-ri-us', 'r_5221931'), ('woonsocket-ri-us', 'r_5225809'), ('cumberland-ri-us', 'r_5221703'), ('coventry-ri-us', 'r_5221637'), ('north-providence-ri-us', 'r_5223681'), ('west-warwick-ri-us', 'r_5225627'), ('johnston-ri-us', 'r_8604682'), ('north-kingstown-ri-us', 'r_5223672'), ('newport-ri-us', 'r_5223593'), ('wakefield-ri-us', 'r_5225455'), ('westerly-ri-us', 'r_5225631'), ('lincoln-ri-us', 'r_8531960'), ('bristol-ri-us', 'r_5221077'), ('central-falls-ri-us', 'r_5221341')],
        'south-carolina': [('charleston-sc-us', 'r_4574324'), ('columbia-sc-us', 'r_4575352'), ('north-charleston-sc-us', 'r_4589387'), ('daniel-island-sc-us', 'r_101183664'), ('mount-pleasant-sc-us', 'r_4588165'), ('rock-hill-sc-us', 'r_4593142'), ('greenville-sc-us', 'r_4580543'), ('orangeburg-sc-us', 'r_4590184'), ('aiken-sc-us', 'r_4569067'), ('florence-sc-us', 'r_4578737')],
        'south-dakota': [('sioux-falls-sd-us', 'r_5231851'), ('rapid-city-sd-us', 'r_5768233'), ('aberdeen-sd-us', 'r_5225857'), ('brookings-sd-us', 'r_5226534'), ('watertown-sd-us', 'r_5232741'), ('mitchell-sd-us', 'r_5229794'), ('yankton-sd-us', 'r_5233053'), ('huron-sd-us', 'r_5228673'), ('spearfish-sd-us', 'r_5769288')],
        'tennessee': [('nashville-tn-us', 'r_4644585'), ('memphis-tn-us', 'r_4641239'), ('metropolitan-government-of-nashville-davidson-balance-tn-us', 'r_101183703'), ('madison-tn-us', 'r_4639035'), ('knoxville-tn-us', 'r_4634946'), ('chattanooga-tn-us', 'r_4612862'), ('clarksville-tn-us', 'r_4613868'), ('east-chattanooga-tn-us', 'r_4619947'), ('murfreesboro-tn-us', 'r_4644312'), ('hermitage-tn-us', 'r_4628929'), ('cookeville-tn-us', 'r_4615145')],
        'texas': [('houston-tx-us', 'r_4699066'), ('hillshire-tx-us', 'r_101183732'), ('bay-area-houston-tx-us', 'r_101183731'), ('bexar-county-tx-us', 'r_4674023'), ('san-antonio-tx-us', 'r_4726206'), ('dallas-tx-us', 'r_4684888'), ('austin-tx-us', 'r_4671654'), ('fort-worth-tx-us', 'r_4691930'), ('el-paso-tx-us', 'r_5520993'), ('ft-worth-tx-us', 'r_101183733'), ('arlington-tx-us', 'r_4671240'), ('corpus-christi-tx-us', 'r_4683416'), ('san-angelo-tx-us', 'r_5530022'), ('killeen-tx-us', 'r_4703223'), ('abilene-tx-us', 'r_4669635'), ('georgetown-tx-us', 'r_4693342')],
        'utah': [('salt-lake-city-ut-us', 'r_5780993'), ('west-valley-city-ut-us', 'r_5784607'), ('west-jordan-ut-us', 'r_5784549'), ('provo-ut-us', 'r_5780026'), ('orem-ut-us', 'r_5779334'), ('sandy-ut-us', 'r_101183793'), ('saint-george-ut-us', 'r_5546220'), ('sandy-city-ut-us', 'r_5781061'), ('ogden-ut-us', 'r_5779206'), ('layton-ut-us', 'r_5777107'), ('south-jordan-ut-us', 'r_5781770'), ('lehi-ut-us', 'r_5777224'), ('millcreek-ut-us', 'r_5778352'), ('taylorsville-ut-us', 'r_5782476'), ('herriman-ut-us', 'r_5775782'), ('logan-ut-us', 'r_5777544'), ('murray-ut-us', 'r_5778755'), ('draper-ut-us', 'r_5774001'), ('spanish-fork-ut-us', 'r_5781860'), ('vernal-ut-us', 'r_5784154')],
        'vermont': [('west-dover-vt-us', 'r_5242678'), ('burlington-vt-us', 'r_5234372'), ('essex-vt-us', 'r_101183887'), ('south-burlington-vt-us', 'r_5241248'), ('colchester-vt-us', 'r_5235024'), ('rutland-vt-us', 'r_5240509'), ('bennington-vt-us', 'r_5233742'), ('brattleboro-vt-us', 'r_5234141'), ('milton-vt-us', 'r_5238609'), ('hartford-vt-us', 'r_5236879'), ('essex-junction-vt-us', 'r_5235952'), ('williston-vt-us', 'r_5243008')],
        'virginia': [('virginia-beach-va-us', 'r_4791259'), ('chesterfield-va-us', 'r_4752250'), ('chesapeake-va-us', 'r_4752186'), ('norfolk-va-us', 'r_4776222'), ('arlington-va-us', 'r_4744709'), ('richmond-va-us', 'r_4781708'), ('arlington-county-va-us', 'r_4744725'), ('newport-news-va-us', 'r_4776024'), ('alexandria-va-us', 'r_4744091'), ('spotsylvania-va-us', 'r_4786946'), ('east-hampton-va-us', 'r_4756955'), ('hampton-va-us', 'r_4762894'), ('petersburg-va-us', 'r_4778626'), ('williamsburg-va-us', 'r_4793846'), ('fredericksburg-va-us', 'r_4760059'), ('charlottesville-va-us', 'r_4752031')],
        'washington': [('whidbey-island-wa-us', 'r_101183934'), ('seattle-wa-us', 'r_5809844'), ('spokane-wa-us', 'r_5811696'), ('tacoma-wa-us', 'r_5812944'), ('vancouver-wa-us', 'r_5814616'), ('bellevue-wa-us', 'r_5786882'), ('kent-wa-us', 'r_5799625'), ('everett-wa-us', 'r_5793933'), ('renton-wa-us', 'r_5808189'), ('spokane-valley-wa-us', 'r_5811729'), ('federal-way-wa-us', 'r_5794245'), ('yakima-wa-us', 'r_5816605'), ('kirkland-wa-us', 'r_5799841'), ('wenatchee-wa-us', 'r_5815342'), ('kennewick-wa-us', 'r_5799610')],
        'west-virginia': [('charleston-wv-us', 'r_4801859'), ('huntington-wv-us', 'r_4809537'), ('parkersburg-wv-us', 'r_4817641'), ('morgantown-wv-us', 'r_4815352'), ('clarksburg-wv-us', 'r_4802316'), ('beckley-wv-us', 'r_4798308')],
        'wisconsin': [('milwaukee-wi-us', 'r_5263045'), ('madison-wi-us', 'r_5261457'), ('green-bay-wi-us', 'r_5254962'), ('kenosha-wi-us', 'r_5258393'), ('wausau-wi-us', 'r_5278120'), ('wisconsin-dells-wi-us', 'r_5279422'), ('la-crosse-wi-us', 'r_5258957'), ('eau-claire-wi-us', 'r_5251436')],
        'wyoming': [('wyoming-us', 'r_5843591'), ('cheyenne-wy-us', 'r_5821086'), ('casper-wy-us', 'r_5820705'), ('gillette-wy-us', 'r_5826027'), ('laramie-wy-us', 'r_5830062'), ('sheridan-wy-us', 'r_5838198'), ('jackson-wy-us', 'r_5828648'), ('riverton-wy-us', 'r_5836665'), ('cody-wy-us', 'r_5821593')]
    })
    
    # ============================================================================
    # SCRAPING PERFORMANCE SETTINGS
    # ============================================================================
    
    # Browser and request settings
    HEADLESS: bool = os.getenv('HEADLESS', 'true').lower() in ('true', '1', 'yes')
    TIMEOUT: int = int(os.getenv('TIMEOUT', '45').strip('"'))  # Browser timeout in seconds
    MAX_PAGES_PER_STATE: int = int(os.getenv('MAX_PAGES_PER_STATE', '50').strip('"'))  # Limit pages per state
    
    # ============================================================================
    # OUTPUT SETTINGS
    # ============================================================================
    
    OUTPUT_DIR: str = os.getenv('OUTPUT_DIR', 'data')
    LOG_DIR: str = os.getenv('LOG_DIR', 'logs')

config = Config()

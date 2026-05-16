//var page =  window.location.pathname;
var tmp_arr =  window.location.pathname.split('/');
// indexの1がairport,lineじゃない場合は多言語によるアクセス
if(tmp_arr[1] != 'airport' && tmp_arr[1] != 'line'){
    // 言語用のプレフィックスを削除
    tmp_arr.splice(1,1);
}
var page = tmp_arr.join('/');
var fileName = {
    
    '/airport/h-ckitaminami/' : {
        'table1' : '/include2/timetable/253.html',
        'table2' : '/include/timetable/253.html',
        'table3' : '/include/timetable/253.html',
        'table4' : '/include2/timetable/253.html',
        'table5' : '/include2/timetable/253.html',
        'table6' : '/include2/timetable/253.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 11番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly2.html'],
            ['センター北駅 5番のりば','/include/line/root_stop/common.html','35.553447,139.577424','18'],
            ['センター南駅 8番のりば','/include/line/root_stop/common.html','35.545663,139.575537','18'],
        ],
        'page_id' : 'AirportCheckHaneSen'
    },
    '/airport/h-disney/' : {
        'table1' : '/include2/timetable/379.html',
        'table2' : '/include/timetable/379.html',
        'table3' : '/include/timetable/379.html',
        'table4' : '/include2/timetable/379.html',
        'table5' : '/include2/timetable/379.html',
        'table6' : '/include2/timetable/379.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 5番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 6番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 5番のりば','/include/line/root_stop/imgonly1.html'],
            ['東京ディズニーランド・バスターミナル・イースト 8番のりば','/include/line/root_stop/common.html','35.63589,139.8812','18'],
            ['ディズニーアンバサダー®ホテル','/include/line/root_stop/common.html','35.633555,139.888221','18'],
            ['東京ディズニーシー・バスターミナル・ノース 4番のりば','/include/line/root_stop/common.html','35.628707,139.88743','18'],
            ['東京ディズニーシー・ホテルミラコスタ®','/include/line/root_stop/common.html','35.627489,139.887291','18'],
            ['東京ディズニーランド®ホテル','/include/line/root_stop/common.html','35.636948,139.877567','18'],
            ['東京ベイ舞浜ホテルファーストリゾート','/include/line/root_stop/common.html','35.631763,139.873175','18'],
            ['舞浜ビューホテル by HULIC','/include/line/root_stop/common.html','35.630612,139.873492','18'],
            ['グランドニッコー東京ベイ 舞浜','/include/line/root_stop/common.html','35.629321,139.874025','18'],
            ['東京ディズニーシー・ファンタジースプリングスホテル','/include/line/root_stop/common.html','35.62879671447207, 139.87601198672837','18'],
            ['シェラトン・グランデ・トーキョーベイ・ホテル','/include/line/root_stop/common.html','35.626386,139.877458','18'],
            ['ホテルオークラ東京ベイ','/include/line/root_stop/common.html','35.626466,139.876208','18'],
            ['東京ディズニーリゾート・トイ・ストーリー®ホテル','/include/line/root_stop/common.html','35.625898,139.874895','18'],
            ['ヒルトン東京ベイ','/include/line/root_stop/common.html','35.627277,139.87374','18'],
        ],
        'page_id' : 'AirportCheckHaneDis'
    },
    // '/airport/h-ebina/' : {
    //     'table1' : '/include2/timetable/194.html',
    //     'table2' : '/include/timetable/194.html',
    //     'table3' : '/include/timetable/194.html',
    //     'table4' : '/include2/timetable/194.html',
    //     'table5' : '/include2/timetable/194.html',
    //     'table6' : '/include2/timetable/194.html',
    //     'bus_stop' : [
    //         ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
    //         ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
    //         ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
    //         ['海老名駅 1番のりば','/include/line/root_stop/common.html','35.452461,139.392085','18'],
    //     ],
    //     'page_id' : 'AirportCheckHaneEbina'
    // },


    '/airport/h-fujimino/' : {
        'table1' : '/include2/timetable/369.html',
        'table2' : '/include/timetable/369.html',
        'table3' : '/include/timetable/369.html',
        'table4' : '/include2/timetable/369.html',
        'table5' : '/include2/timetable/369.html',
        'table6' : '/include2/timetable/369.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['第三中学校','/include/line/root_stop/common.html','35.808093,139.587378','18'],
            ['朝霞台駅南口 3番のりば','/include/line/root_stop/common.html','35.814434,139.586217','18'],
            ['志木駅南口 2番のりば','/include/line/root_stop/common.html','35.821961,139.574394','18'],
            ['新座車庫','/include/line/root_stop/common.html','35.815012,139.555094','18'],
            ['ふじみ野駅西口 2番のりば','/include/line/root_stop/common.html','35.860566,139.522443','18'],
        ],
        'page_id' : 'AirportCheckHaneAsaka'
    },
    '/airport/h-fujisawa/' : {
        'table1' : '/include2/timetable/263.html',
        'table2' : '/include/timetable/263.html',
        'table3' : '/include/timetable/263.html',
        'table4' : '/include2/timetable/263.html',
        'table5' : '/include2/timetable/263.html',
        'table6' : '/include2/timetable/263.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['大船駅 東口7番のりば','/include/line/root_stop/ohfuna.html','35.351857,139.531076','18'],
            ['藤沢駅 南口7番のりば','/include/line/root_stop/common.html','35.3378,139.487574','18'],
            // ['鎌倉駅 東口2番のりば','/include/line/root_stop/kamakura.html'],
        ],
        'page_id' : 'AirportCheckHaneFuji'
    },
    '/airport/h-funabashi/' : {
        'table1' : '/include2/timetable/230.html',
        'table2' : '/include/timetable/230.html',
        'table3' : '/include/timetable/230.html',
        'table4' : '/include2/timetable/230.html',
        'table5' : '/include2/timetable/230.html',
        'table6' : '/include2/timetable/230.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番（深夜6番）のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番（深夜15番）のりば','/include/line/root_stop/imgonly2.html'],
            ['西船橋駅 北口7番のりば','/include/line/root_stop/common.html','35.708219,139.958569','18'],
            ['船橋駅 南口2番のりば','/include/line/root_stop/common.html','35.701277,139.985672','18'],
        ],
        'page_id' : 'AirportCheckHaneNishifuna'
    },
    '/airport/h-futamata/' : { 
        'table1' : '/include2/timetable/378.html',
        'table2' : '/include/timetable/378.html',
        'table3' : '/include/timetable/378.html',
        'table4' : '/include2/timetable/378.html',
        'table5' : '/include2/timetable/378.html',
        'table6' : '/include2/timetable/378.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 11番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly2.html'],
            ['二俣川駅 北口０番のりば','/include/line/root_stop/common.html','35.464099,139.532657','18'],
        ],
        'page_id' : 'AirportCheckHaneFuta'
    },  
    '/airport/h-goi/' : {
        'table1' : '/include2/timetable/168.html',
        'table2' : '/include/timetable/168.html',
        'table3' : '/include/timetable/168.html',
        'table4' : '/include2/timetable/168.html',
        'table5' : '/include2/timetable/168.html',
        'table6' : '/include2/timetable/168.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['市原駐車場','/include/line/root_stop/common.html','35.501695,140.089223','18'],
            ['五井駅東口 1番のりば','/include/line/root_stop/common.html','35.51285,140.090037','18'],
            ['季美の森・南センター前','/include/line/root_stop/common.html','35.54935,140.3018','18'],
            ['季美の森・むぎわら公園','/include/line/root_stop/common.html','35.55238,140.3061','18'],
            ['東金駅東口','/include/line/root_stop/common.html','35.560135,140.364098','18'],
        ],
        'page_id' : 'AirportCheckHanegoi'
    },
    '/airport/h-gotenba/' : {
        'table1' : '/include2/timetable/311.html',
        'table2' : '/include/timetable/311.html',
        'table3' : '/include/timetable/311.html',
        'table4' : '/include2/timetable/311.html',
        'table5' : '/include2/timetable/311.html',
        'table6' : '/include2/timetable/311.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['横浜駅（YCAT） 5番のりば','/include/line/root_stop/ycat.html'],
            ['東名秦野','/include/line/root_stop/common.html','35.35237,139.2343','18'],
            ['東名大井','/include/line/root_stop/common.html','35.34052,139.165','18'],
            ['東名松田','/include/line/root_stop/common.html','35.3508,139.1354','18'],
            ['東名山北','/include/line/root_stop/common.html','35.3643,139.1024','18'],
            ['東名小山','/include/line/root_stop/common.html','35.354397,138.986866','18'],
            ['東名足柄','/include/line/root_stop/common.html','35.328309,138.971962','18'],
            ['御殿場インター前','/include/line/root_stop/common.html','35.294083,138.945317','18'],
            ['御殿場駅 乙女口3番のりば','/include/line/root_stop/imgonly_gotenba.html'],
            ['箱根仙石案内所','/include/line/root_stop/common.html','35.27126,139.0101','18'],
            ['仙郷楼前','/include/line/root_stop/common.html','35.26441,139.0139','18'],
            ['仙石高原','/include/line/root_stop/common.html','35.25883,139.000776','18'],
            ['南温泉荘','/include/line/root_stop/common.html','35.244241,138.998843','18'],
            ['箱根桃源台 2番のりば','/include/line/root_stop/common.html','35.23779,138.995','18'],
        ],
        'page_id' : 'AirportCheckHaneGoten'
    },
    '/airport/h-honatsugi/' : {
        'table1' : '/include2/timetable/368.html',
        'table2' : '/include/timetable/368.html',
        'table3' : '/include/timetable/368.html',
        'table4' : '/include2/timetable/368.html',
        'table5' : '/include2/timetable/368.html',
        'table6' : '/include2/timetable/368.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['東名大和 (高速道路上)','/include/line/root_stop/common.html','35.479673,139.453996','18'],
            ['本厚木駅 北口3番のりば','/include/line/root_stop/common.html','35.439905,139.363286','18'],
            ['田村車庫','/include/line/root_stop/common.html','35.376026,139.3585','18'],
        ],
        'page_id' : 'AirportCheckHaneAtsugi'
    },
    '/airport/h-htotsuka/' : {
        'table1' : '/include2/timetable/62.html',
        'table2' : '/include/timetable/62.html',
        'table3' : '/include/timetable/62.html',
        'table4' : '/include2/timetable/62.html',
        'table5' : '/include2/timetable/62.html',
        'table6' : '/include2/timetable/62.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['東戸塚駅 2番のりば','/include/line/root_stop/common.html','35.43059,139.557249','18'],
            ['上永谷駅 1番のりば','/include/line/root_stop/common.html','35.401126,139.571287','18'],
            ['港南台駅 6番のりば','/include/line/root_stop/common.html','35.374739,139.576926','18'],
            ['戸塚駅 東口6番のりば','/include/line/root_stop/common.html','35.400991,139.534497','18'],
        ],
        'page_id' : 'AirportCheckHaneTotsuka'
    },
    '/airport/h-htotsuka/index_20200901.html' : {
        'table1' : '/include2/timetable/242.html',
        'table2' : '/include/timetable/242.html',
        'table3' : '/include/timetable/242.html',
        'table4' : '/include2/timetable/242.html',
        'table5' : '/include2/timetable/242.html',
        'table6' : '/include2/timetable/242.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['東戸塚駅 2番のりば','/include/line/root_stop/common.html','35.43059,139.557249','18'],
            ['上永谷駅 1番のりば','/include/line/root_stop/common.html','35.401126,139.571287','18'],
            ['港南台駅 6番のりば','/include/line/root_stop/common.html','35.374739,139.576926','18'],
            ['戸塚駅 東口6番のりば','/include/line/root_stop/common.html','35.400991,139.534497','18'],
        ],
        'page_id' : 'AirportCheckHaneTotsuka'
    },
    '/airport/hi-chiba/' : {
        'table1' : '/include/timetable/220.html',
        'table2' : '/include2/timetable/220.html',
        'table3' : '/include/timetable/220.html',
        'table4' : '/include2/timetable/220.html',
        'table5' : '/include2/timetable/220.html',
        'table6' : '/include2/timetable/220.html',
        'bus_stop' : [
            ['羽田空港（第3ターミナル） 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港（第2ターミナル） 15番のりば','/include/line/root_stop/imgonly2.html'],
        ],
        'page_id' : 'AirportCheckHanekokuMaku'
    },
    '/airport/hi-funabashi/' : {
        'table1' : '/include/timetable/221.html',
        'table2' : '/include2/timetable/221.html',
        'table3' : '/include/timetable/221.html',
        'table4' : '/include2/timetable/221.html',
        'table5' : '/include2/timetable/221.html',
        'table6' : '/include2/timetable/221.html',
        'bus_stop' : [
            ['羽田空港（第3ターミナル） 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港（第2ターミナル） 15番のりば','/include/line/root_stop/imgonly2.html'],
        ],
        'page_id' : 'AirportCheckHanekokuNishifuna'
    },
    '/airport/hi-kamata/' : {
        'table1' : '/include/timetable/410.html',
        'table2' : '/include2/timetable/410.html',
        'table3' : '/include/timetable/410.html',
        'table4' : '/include2/timetable/410.html',
        'table5' : '/include2/timetable/410.html',
        'table6' : '/include2/timetable/410.html',
        'bus_stop' : [
            ['羽田空港第2ターミナル 1階到着ロビー 17番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['蒲田駅 東口4番のりば','/include/line/root_stop/kamata.html'],
        ],
        'page_id' : 'AirportCheckHanekokuKamata'
    },
    '/airport/hi-kawasaki/' : {
        'table1' : '/include2/timetable/214.html',
        'table2' : '/include/timetable/214.html',
        'table3' : '/include/timetable/214.html',
        'table4' : '/include2/timetable/214.html',
        'table5' : '/include2/timetable/214.html',
        'table6' : '/include2/timetable/214.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 17番のりば','/include/line/root_stop/imgonly2.html'],
            ['川崎駅 東口18番のりば','/include/line/root_stop/kawasaki.html'],
            ['蒲田駅 東口0番のりば','/include/line/root_stop/kamata_e0.html'], /* Not publish */
            ['大鳥居','/include/line/root_stop/common.html','35.5524,139.7412','18'],
        ],
        'page_id' : 'AirportCheckHanekokuOotorii'
    },
    '/airport/hi-mm/' : {
        'table1' : '/include2/timetable/332.html',
        'table2' : '/include/timetable/332.html',
        'table3' : '/include/timetable/332.html',
        'table4' : '/include2/timetable/332.html',
        'table5' : '/include2/timetable/332.html',
        'table6' : '/include2/timetable/332.html',
        'bus_stop' : [
            ['羽田空港（第3ターミナル） 7番のりば','/include/line/root_stop/imgonly0.html'],
            // ['羽田空港（第2ターミナル） 16番のりば','/include/line/root_stop/imgonly2.html'],
            // ['横浜ロイヤルパークホテル 正面玄関','/include/line/root_stop/common.html','35.454352,139.631799','18'],
            // ['横浜ベイホテル東急 正面玄関','/include/line/root_stop/common.html','35.456861,139.635443','18'],
            // ['ヨコハマグランドインターコンチネンタルホテル（パシフィコ横浜） ホテル正面玄関','/include/line/root_stop/common.html','35.457972,139.636773','18'],
            // ['国際橋・カップヌードルミュージアム前（横浜みなとみらい万葉倶楽部）','/include/line/root_stop/common.html','35.455144,139.638729','18'],
            // ['桜木町駅 7番のりば','/include/line/root_stop/common.html','35.451466,139.632023','18'],
            // [' 横浜駅 （YCAT）  1番のりば','/include/line/root_stop/ycat.html'],
        ],
        'page_id' : 'AirportCheckHanekokuYokoMinachiku'
    },
    '/airport/hi-nikotama/' : {
        'table1' : '/include2/timetable/216.html',
        'table2' : '/include/timetable/216.html',
        'table3' : '/include/timetable/216.html',
        'table4' : '/include2/timetable/216.html',
        'table5' : '/include2/timetable/216.html',
        'table6' : '/include2/timetable/216.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['二子玉川ライズ・楽天クリムゾンハウス','/include/line/root_stop/common.html','35.610132,139.629994','18'],
            ['二子玉川駅（降車のみ）','/include/line/root_stop/common.html','35.611371,139.628719','18'],
            ['渋谷マークシティ 5階92番のりば','/include/line/root_stop/shibuya92.html','35.658419,139.698812','18'],
            ['渋谷駅 西口36番のりば','/include/line/root_stop/common.html','35.657862,139.70105','18'],
            ['セルリアンタワー東急ホテル 地下1階バスのりば','/include/line/root_stop/common.html','35.656351,139.699627','18'],
            ['六本木ヒルズ 団体バス乗降所','/include/line/root_stop/common.html','35.660463,139.72925','18'],
        ],
        'page_id' : 'AirportCheckHanekokuRoppongi'
    },
    '/airport/hi-odaiba/' : {
        'table1' : '/include2/timetable/74.html',
        'table2' : '/include/timetable/74.html',
        'table3' : '/include/timetable/74.html',
        'table4' : '/include2/timetable/74.html',
        'table5' : '/include2/timetable/74.html',
        'table6' : '/include2/timetable/74.html',
        'bus_stop' : [
            ['羽田空港国際線ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['シナガワグース EXインエントランス','/include/line/root_stop/common.html','35.63019,139.7364','18'],
            ['品川駅東口（港南口）','/include/line/root_stop/common.html','35.629584,139.742205','18'],
            ['グランドニッコー東京 台場 2階エントランス','/include/line/root_stop/common.html','35.625131,139.771379','18'],
            ['大江戸温泉物語','/include/line/root_stop/common.html','35.61616,139.7778','18'],
        ],
        'page_id' : 'AirportCheckHanekokuOdaiba'
    },
    '/airport/hi-omori/' : {
        'table1' : '/include/timetable/411.html',
        'table2' : '/include2/timetable/411.html',
        'table3' : '/include/timetable/411.html',
        'table4' : '/include2/timetable/411.html',
        'table5' : '/include2/timetable/411.html',
        'table6' : '/include2/timetable/411.html',
        'bus_stop' : [
            ['羽田空港第2ターミナル 1階到着ロビー 17番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['大森駅 東口3番のりば','/include/line/root_stop/ohmori.html'],
        ],
        'page_id' : 'AirportCheckHanekokuOomori'
    },
    '/airport/hi-saitama/' : {
        'table1' : '/include/timetable/222.html',
        'table2' : '/include2/timetable/222.html',
        'table3' : '/include/timetable/222.html',
        'table4' : '/include2/timetable/222.html',
        'table5' : '/include2/timetable/222.html',
        'table6' : '/include2/timetable/222.html',
        'bus_stop' : [
            ['羽田空港（第3ターミナル）2番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港（第2ターミナル）8番のりば','/include/line/root_stop/imgonly2.html'],
        ],
        'page_id' : 'AirportCheckHanekokuSaitama'
    },
    '/airport/hi-shibuya/' : {
        'table1' : '/include/timetable/223.html',
        'table2' : '/include2/timetable/223.html',
        'table3' : '/include/timetable/223.html',
        'table4' : '/include2/timetable/223.html',
        'table5' : '/include2/timetable/223.html',
        'table6' : '/include2/timetable/223.html',
        'bus_stop' : [
            ['羽田空港（第3ターミナル） 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港（第2ターミナル） 15番のりば','/include/line/root_stop/imgonly2.html'],
        ],
        'page_id' : 'AirportCheckHanekokuShibuya'
    },
    '/airport/hi-yokohama/' : {
        'table1' : '/include/timetable/96.html',
        'table2' : '/include2/timetable/96.html',
        'table3' : '/include/timetable/96.html',
        'table4' : '/include2/timetable/96.html',
        'table5' : '/include2/timetable/96.html',
        'table6' : '/include2/timetable/96.html',
        'bus_stop' : [
            [' 横浜駅 （YCAT）  1番のりば','/include/line/root_stop/ycat.html'],
        ],
        'page_id' : 'AirportCheckHanekokuYoko'
    },
    '/airport/hi-yprince/' : {
        'table1' : '/include/timetable/122.html',
        'table2' : '/include2/timetable/122.html',
        'table3' : '/include/timetable/122.html',
        'table4' : '/include2/timetable/122.html',
        'table5' : '/include2/timetable/122.html',
        'table6' : '/include2/timetable/122.html',
        'bus_stop' : [
            ['羽田空港（第3ターミナル）7番のりば','/include/line/root_stop/imgonly0.html'],
        ],
        'page_id' : 'AirportCheckHanekokuShinyoko'
    },
    '/airport/h-kamakura/' : {
        'table1' : '/include2/timetable/263.html',
        'table2' : '/include/timetable/263.html',
        'table3' : '/include/timetable/263.html',
        'table4' : '/include2/timetable/263.html',
        'table5' : '/include2/timetable/263.html',
        'table6' : '/include2/timetable/263.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['大船駅 東口7番のりば','/include/line/root_stop/common.html','35.351857,139.531076','18'],
            ['鎌倉駅 東口2番のりば','/include/line/root_stop/kamakura.html','35.319357,139.551085','18'],
        ],
        'page_id' : 'AirportCheckHaneKamakura'
    },
    '/airport/h-kamata/' : {
        'table1' : '/include/timetable/98.html',
        'table2' : '/include2/timetable/98.html',
        'table3' : '/include/timetable/98.html',
        'table4' : '/include2/timetable/98.html',
        'table5' : '/include2/timetable/98.html',
        'table6' : '/include2/timetable/98.html',
        'bus_stop' : [
            ['羽田空港第2ターミナル 1階到着ロビー 17番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第3ターミナル 11番のりば（深夜・早朝バスとシャトルバス最終便は8番のりば）','/include/line/root_stop/imgonly0.html'],
            ['蒲田駅 東口0番・3番・4番のりば','/include/line/root_stop/kamata.html'],
        ],
        'page_id' : 'AirportCheckHaneKamata'
    },
    '/airport/h-karuizawa/' : {
        'table1' : '/include2/timetable/82.html',
        'table2' : '/include/timetable/82.html',
        'table3' : '/include/timetable/82.html',
        'table4' : '/include2/timetable/82.html',
        'table5' : '/include2/timetable/82.html',
        'table6' : '/include2/timetable/82.html',
        'bus_stop' : [
            ['横浜駅 東口バスターミナル18番のりば','/include/line/root_stop/yokohama.html'],
            ['品川プリンスホテル','/include/line/root_stop/common.html','35.627661,139.737176','18'],
            ['羽田空港国際線ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['軽井沢７２ゴルフ','/include/line/root_stop/common.html','36.311878,138.631505','18'],
            ['ショッピングプラザ前','/include/line/root_stop/common.html','36.33757,138.6316','18'],
            ['軽井沢プリンスホテルウエスト','/include/line/root_stop/common.html','36.336959,138.63291','18'],
            ['軽井沢駅前 北口3番のりば','/include/line/root_stop/common.html','36.34304,138.6369','18'],
            ['軽井沢プリンスホテルスキー場 【冬季限定】','/include/line/root_stop/common.html','36.340692,138.643002','18'],
        ],
        'page_id' : 'AirportCheckHaneKarui'
    },
    '/airport/h-kashima/' : {
        'table1' : '/include2/timetable/154.html',
        'table2' : '/include/timetable/154.html',
        'table3' : '/include/timetable/154.html',
        'table4' : '/include2/timetable/154.html',
        'table5' : '/include2/timetable/154.html',
        'table6' : '/include2/timetable/154.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['水郷潮来','/include/line/root_stop/common.html','35.93825,140.5853','18'],
            ['鹿島セントラルホテル','/include/line/root_stop/common.html','35.89916,140.6385','18'],
            ['鹿島製鉄所','/include/line/root_stop/common.html','35.93855,140.6609','18'],
            ['鹿島宇宙センター','/include/line/root_stop/common.html','35.954583,140.662108','18'],
            ['鹿嶋市役所','/include/line/root_stop/common.html','35.96532,140.6448','18'],
            ['鹿島神宮','/include/line/root_stop/common.html','35.96586,140.6322','18'],
            ['鹿島神宮駅 2番のりば','/include/line/root_stop/common.html','35.97033,140.6261','18'],
        ],
        'page_id' : 'AirportCheckHaneKashima'
    },
    '/airport/h-kasiwanishi/' : {
        'table1' : '/include2/timetable/371.html',
        'table2' : '/include/timetable/372.html',
        'table3' : '/include/timetable/371.html',
        'table4' : '/include2/timetable/372.html',
        'table5' : '/include2/timetable/372.html',
        'table6' : '/include2/timetable/372.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['流山おおたかの森駅 西口 6番のりば','/include/line/root_stop/common.html','35.872560,139.924200','18'],
            ['国立がん研究センター','/include/line/root_stop/common.html','35.901725,139.941194','18'],
            ['柏の葉キャンパス駅 西口2番のりば','/include/line/root_stop/common.html','35.894096,139.952544','18'],
            ['三間','/include/line/root_stop/common.html','35.870641,139.951803','18'],
            ['向原住宅','/include/line/root_stop/common.html','35.866346,139.959083','18'],
            ['柏駅西口','/include/line/root_stop/common.html','35.864574,139.970056','18'],
        ],
        'page_id' : 'AirportCheckHanekashiwa'
    },
    // '/airport/h-katsunuma/' : {
    //     'table1' : '/include2/timetable/69.html',
    //     'table2' : '/include/timetable/69.html',
    //     'table3' : '/include/timetable/69.html',
    //     'table4' : '/include2/timetable/69.html',
    //     'table5' : '/include2/timetable/69.html',
    //     'table6' : '/include2/timetable/69.html',
    //     'bus_stop' : [
    //         ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
    //         ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
    //         ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
    //         ['勝沼','/include/line/root_stop/common.html','35.65179,138.7294','18'],
    //         ['一宮','/include/line/root_stop/common.html','35.64423,138.6923','18'],
    //         ['石和','/include/line/root_stop/common.html','35.650119,138.638615','18'],
    //         ['山梨学院大学','/include/line/root_stop/common.html','35.65788,138.6014','18'],
    //         ['甲府駅 南口6番のりば','/include/line/root_stop/common.html','35.666397, 138.568459','18'],
    //         ['竜王','/include/line/root_stop/common.html','35.667803,138.521307','18'],
    //     ],
    //     'page_id' : 'AirportCheckHaneKatsunuma'
    // },
    '/airport/h-katsunuma/' : {
        'table1' : '/include2/timetable/258.html',
        'table2' : '/include/timetable/258.html',
        'table3' : '/include/timetable/258.html',
        'table4' : '/include2/timetable/258.html',
        'table5' : '/include2/timetable/258.html',
        'table6' : '/include2/timetable/258.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['横浜駅（YCAT）6番のりば','/include/line/root_stop/ycat.html'],
            ['勝沼','/include/line/root_stop/common.html','35.65179,138.7294','18'],
            ['一宮','/include/line/root_stop/common.html','35.64423,138.6923','18'],
            ['石和','/include/line/root_stop/common.html','35.650119,138.638615','18'],
            ['山梨学院大学','/include/line/root_stop/common.html','35.65788,138.6014','18'],
            ['甲府駅 南口6番のりば','/include/line/root_stop/common.html','35.666397, 138.568459','18'],
            ['竜王','/include/line/root_stop/common.html','35.667803,138.521307','18'],
        ],
        'page_id' : 'AirportCheckHaneKatsunuma'
    },
    '/airport/h-kawaguchi/' : {
        'table1' : '/include2/timetable/316.html',
        'table2' : '/include/timetable/316.html',
        'table3' : '/include/timetable/316.html',
        'table4' : '/include2/timetable/316.html',
        'table5' : '/include2/timetable/316.html',
        'table6' : '/include2/timetable/316.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['王子駅南口','/include/line/root_stop/common.html','35.752155,139.739807','18'],
            ['赤羽駅東口 9番のりば','/include/line/root_stop/common.html','35.778764,139.722686','18'],
            ['川口駅東口 6番のりば','/include/line/root_stop/common.html','35.8022,139.718553','18'],
            ['川口元郷駅 4番のりば ','/include/line/root_stop/common.html','35.801423,139.730498','18'],
        ],
        'page_id' : 'AirportCheckHaneouji'
    },
    '/airport/h-kawaguhiko/' : {
        'table1' : '/include2/timetable/318.html',
        'table2' : '/include/timetable/318.html',
        'table3' : '/include/timetable/318.html',
        'table4' : '/include2/timetable/318.html',
        'table5' : '/include2/timetable/318.html',
        'table6' : '/include2/timetable/318.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['品川駅東口（港南口）','/include/line/root_stop/common.html','35.629584,139.742205','18'],
            ['富士急ハイランド','/include/line/root_stop/common.html','35.48467,138.7769','18'],
            ['河口湖駅 2番のりば','/include/line/root_stop/common.html','35.498325,138.768372','18'],
            ['富士山駅 1番のりば','/include/line/root_stop/common.html','35.483811,138.795535','18'],
        ],
        'page_id' : 'AirportCheckHaneKawaguchi'
    },
    '/airport/h-kawasaki/' : {
        'table1' : '/include/timetable/99.html',
        'table2' : '/include2/timetable/99.html',
        'table3' : '/include/timetable/99.html',
        'table4' : '/include2/timetable/99.html',
        'table5' : '/include2/timetable/99.html',
        'table6' : '/include2/timetable/99.html',
        'bus_stop' : [
            ['羽田空港第2ターミナル 1階到着ロビー 17番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第3ターミナル 11番のりば','/include/line/root_stop/imgonly0.html'],
            ['川崎駅 東口18番のりば','/include/line/root_stop/kawasaki.html'],
        ],
        'page_id' : 'AirportCheckHaneKawasaki'
    },
    '/airport/h-daishibashi/' : {
        'table1' : '/include/timetable/99.html',
        'table2' : '/include2/timetable/99.html',
        'table3' : '/include/timetable/99.html',
        'table4' : '/include2/timetable/99.html',
        'table5' : '/include2/timetable/99.html',
        'table6' : '/include2/timetable/99.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 11番のりば','/include/line/root_stop/imgonly0.html'],
            ['大師橋駅 3番のりば','/include/line/root_stop/common.html','35.53643, 139.74001','18'],
        ],
        'page_id' : 'AirportCheckHaneDaishibashi'
    },
    '/airport/h-kichijyoji/' : {
        'table1' : '/include2/timetable/200.html',
        'table2' : '/include/timetable/200.html',
        'table3' : '/include/timetable/200.html',
        'table4' : '/include2/timetable/200.html',
        'table5' : '/include2/timetable/200.html',
        'table6' : '/include2/timetable/200.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 9番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 10番のりば','/include/line/root_stop/imgonly2.html'],
            ['吉祥寺駅 中央口10番のりば','/include/line/root_stop/common.html','35.70302,139.58085','18'],
        ],
        'page_id' : 'AirportCheckHaneKichijoji'
    },
    '/airport/h-kimitsu/' : {
        'table1' : '/include2/timetable/404.html',
        'table2' : '/include/timetable/404.html',
        'table3' : '/include/timetable/404.html',
        'table4' : '/include2/timetable/404.html',
        'table5' : '/include2/timetable/404.html',
        'table6' : '/include2/timetable/404.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['木更津羽鳥野バストップ','/include/line/root_stop/common.html','35.34729,139.9445','18'],
            ['君津バスターミナル 2番のりば','/include/line/root_stop/common.html','35.318561,139.935738','18'],
            ['杢師四丁目','/include/line/root_stop/common.html','35.3193,139.9174','18'],
            ['君津市役所','/include/line/root_stop/common.html','35.32921,139.9018','18'],
            ['君津駅南口 6番のりば','/include/line/root_stop/common.html','35.33341,139.8947','18'],
        ],
        'page_id' : 'AirportCheckHaneKimitsu'
    },
    '/airport/h-kisarazu/' : {
        'table1' : '/include2/timetable/402.html',
        'table2' : '/include2/timetable/403.html',
        'table3' : '/include/timetable/402.html',
        'table4' : '/include/timetable/403.html',
        'table5' : '/include2/timetable/403.html',
        'table6' : '/include/timetable/403.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['木更津金田バスターミナル 5番のりば','/include/line/root_stop/common.html','35.431568,139.920896','18'],
            ['袖ヶ浦バスターミナル 4番のりば','/include/line/root_stop/common.html','35.417853,139.956874','18'],
            ['木更津駅東口 8番のりば','/include/line/root_stop/common.html','35.381789,139.926889','18'],
        ],
        'page_id' : 'AirportCheckHaneKisa'
    },
    '/airport/h-kitasenjyu/' : {
        'table1' : '/include2/timetable/401.html',
        'table2' : '/include/timetable/401.html',
        'table3' : '/include/timetable/401.html',
        'table4' : '/include2/timetable/401.html',
        'table5' : '/include2/timetable/401.html',
        'table6' : '/include2/timetable/401.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 7番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 8番のりば','/include/line/root_stop/imgonly2.html'],
            ['千住大橋駅','/include/line/root_stop/common.html','35.741971,139.796827','18'],
            ['北千住駅 西口4番のりば','/include/line/root_stop/common.html','35.750313,139.804383','18'],
        ],
        'page_id' : 'AirportCheckHaneKitasen'
    },
    '/airport/h-machida/' : {
        'table1' : '/include2/timetable/367.html',
        'table2' : '/include/timetable/367.html',
        'table3' : '/include/timetable/367.html',
        'table4' : '/include2/timetable/367.html',
        'table5' : '/include2/timetable/367.html',
        'table6' : '/include2/timetable/367.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['南町田グランベリーパーク駅 1番のりば','/include/line/root_stop/common.html','35.512017,139.470344','18'],
            ['町田バスセンター 6番のりば','/include/line/root_stop/common.html','35.543527,139.444442','18'],
            ['相模大野駅 北口6番のりば','/include/line/root_stop/common.html','35.531524,139.436679','18'],
            ['相模大野立体駐車場 1番のりば','/include/line/root_stop/common.html','35.533731,139.435308','18'],
        ],
        'page_id' : 'AirportCheckHaneTamachi'
    },
    '/airport/h-mkosugi/' : {
        'table1' : '/include2/timetable/409.html',
        'table2' : '/include/timetable/409.html',
        'table3' : '/include/timetable/409.html',
        'table4' : '/include2/timetable/409.html',
        'table5' : '/include2/timetable/409.html',
        'table6' : '/include2/timetable/409.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 10番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly2.html'],
            ['武蔵新田駅','/include/line/root_stop/common.html','35.568277,139.692783','18'],
            ['久が原駅入口','/include/line/root_stop/common.html','35.579268,139.683056','18'],
            ['田園調布本町','/include/line/root_stop/common.html','35.588138,139.675644','18'],
            ['武蔵小杉駅東口 3番のりば','/include/line/root_stop/common.html','35.575786,139.660452','18'],
            ['武蔵小杉駅（横須賀線口） 2番のりば','/include/line/root_stop/common.html','35.573267,139.662635','18'],
        ],
        'page_id' : 'AirportCheckHaneMusashi'
    },
    '/airport/h-nikko/' : {
        'table1' : '/include2/timetable/162.html',
        'table2' : '/include/timetable/162.html',
        'bus_stop' : [
            ['横浜駅 東口バスターミナル16番のりば','/include/line/root_stop/yokohama.html'],
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['下今市駅 2番のりば','/include/line/root_stop/common.html','36.725364,139.692426','18'],
            ['東武日光駅        2Eのりば','/include/line/root_stop/common.html','36.747593,139.620234','18'],
            ['東武ワールドスクウェア駅','/include/line/root_stop/common.html','36.809070,139.709731','18'],
            ['鬼怒川温泉駅 10番のりば','/include/line/root_stop/common.html','36.823724,139.716783','18'],
        ],
        'page_id' : 'AirportCheckHaneNikko'
    }, 
    '/airport/h-nikotama/' : {
        'table1' : '/include2/timetable/285.html',
        'table2' : '/include/timetable/285.html',
        'table3' : '/include/timetable/285.html',
        'table4' : '/include2/timetable/285.html',
        'table5' : '/include2/timetable/285.html',
        'table6' : '/include2/timetable/285.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 7番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 8番のりば','/include/line/root_stop/imgonly2.html'],
            ['二子玉川ライズ・楽天クリムゾンハウス','/include/line/root_stop/common.html','35.610132,139.629994','18'],
        ],
        'page_id' : 'AirportCheckHaneFutako'
    },
    '/airport/h-oimachi/' : {
        'table1' : '/include2/timetable/394.html',
        'table2' : '/include/timetable/394.html',
        'table3' : '/include/timetable/394.html',
        'table4' : '/include2/timetable/394.html',
        'table5' : '/include2/timetable/394.html',
        'table6' : '/include2/timetable/394.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 10番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly2.html'],
            ['品川シーサイド駅 2番のりば','/include/line/root_stop/common.html','35.609234,139.749624','18'],
            ['大井町駅  西口3番のりば','/include/line/root_stop/oimachi.html'],
            ['大崎駅西口 バスターミナル1～3番のりば','/include/line/root_stop/common.html','35.61816,139.7287','18'],
            ['武蔵小山駅 1番のりば','/include/line/root_stop/common.html','35.620101, 139.703702','18'],
        ],
        'page_id' : 'AirportCheckHaneSee'
    },
    '/airport/h-omori/' : {
        'table1' : '/include/timetable/100.html',
        'table2' : '/include2/timetable/100.html',
        'table3' : '/include/timetable/100.html',
        'table4' : '/include2/timetable/100.html',
        'table5' : '/include2/timetable/100.html',
        'table6' : '/include2/timetable/100.html',
        'bus_stop' : [
            ['羽田空港第2ターミナル 1階到着ロビー 17番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第3ターミナル 11番のりば（深夜・早朝バスは8番のりば）','/include/line/root_stop/imgonly0.html'],
            ['大森駅 東口3番のりば','/include/line/root_stop/ohmori.html'],
        ],
        'page_id' : 'AirportCheckHaneOomori'
    },
    '/airport/h-ootaki/' : {
        'table1' : '/include/timetable/166.html',
        'table2' : '/include2/timetable/166.html',
        'table3' : '/include/timetable/166.html',
        'table4' : '/include2/timetable/166.html',
        'table5' : '/include2/timetable/166.html',
        'table6' : '/include2/timetable/166.html',
        'bus_stop' : [
            ['シナガワグース EXインエントランス','/include/line/root_stop/common.html','35.63019,139.7364','18'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly2.html'],
            ['大多喜','/include/line/root_stop/common.html','35.28902,140.2537','18'],
            ['大多喜駅','/include/line/root_stop/common.html','35.28693,140.2443','18'],
        ],
        'page_id' : 'AirportCheckHaneOotaki'
    },
    '/airport/h-saitama/' : {
        'table1' : '/include2/timetable/203.html',
        'table2' : '/include/timetable/203.html',
        'table3' : '/include/timetable/203.html',
        'table4' : '/include2/timetable/203.html',
        'table5' : '/include2/timetable/203.html',
        'table6' : '/include2/timetable/203.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 2番（深夜2番）のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 7番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 8番（深夜8番）のりば','/include/line/root_stop/imgonly2.html'],
            ['さいたま新都心 西口3番のりば','/include/line/root_stop/common.html','35.893398,139.631748','18'],
            ['大宮駅西口 そごう前 10番のりば','/include/line/root_stop/common.html','35.905183,139.622021','18'],
            ['西武バス大宮営業所','/include/line/root_stop/common.html','35.908211,139.598783','18'],
        ],
        'page_id' : 'AirportCheckHaneSaitama'
    },
    '/airport/h-sheraton/' : {
        'table1' : '/include2/timetable/158.html',
        'table2' : '/include/timetable/158.html',
        'table3' : '/include/timetable/158.html',
        'table4' : '/include2/timetable/158.html',
        'table5' : '/include2/timetable/158.html',
        'table6' : '/include2/timetable/158.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 10番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 11番のりば','/include/line/root_stop/imgonly2.html'],
            ['横浜ベイシェラトン ホテル＆タワーズ（横浜駅西口）正面玄関','/include/line/root_stop/common.html','35.46681,139.619983','18'],
        ],
        'page_id' : 'AirportCheckHaneSheraton'
    },
        '/airport/h-shibuya/' : {
        'table1' : '/include2/timetable/387.html',
        'table2' : '/include2/timetable/387.html',
        'table3' : '/include/timetable/387.html',
        'table4' : '/include/timetable/387.html',
        'table5' : '/include2/timetable/387.html',
        'table6' : '/include2/timetable/387.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番（深夜・早朝6番）のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 9番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 10番（深夜15番）のりば','/include/line/root_stop/imgonly2.html'],
            ['セルリアンタワー東急ホテル 地下1階バスのりば','/include/line/root_stop/common.html','35.656351,139.699627','18'],
            ['渋谷駅 マークシティ5階92番のりば','/include/line/root_stop/shibuya92.html','35.658419,139.698812','18'],
            ['渋谷フクラス 9番のりば','/include/line/root_stop/common.html','35.6577,139.700312','18'],
        ],
        'page_id' : 'AirportCheckHaneShibuya'
    },
    '/airport/h-shinyuri/' : {
        'table1' : '/include2/timetable/377.html',
        'table2' : '/include/timetable/377.html',
        'table3' : '/include/timetable/377.html',
        'table4' : '/include2/timetable/377.html',
        'table5' : '/include2/timetable/377.html',
        'table6' : '/include2/timetable/377.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['新百合ヶ丘駅 南口8番のりば','/include/line/root_stop/common.html','35.602953,139.507483','18'],
        ],
        'page_id' : 'AirportCheckHaneShinyuri'
    },
    '/airport/h-skytree/' : {
        'table1' : '/include2/timetable/352.html',
        'table2' : '/include/timetable/352.html',
        'table3' : '/include/timetable/352.html',
        'table4' : '/include2/timetable/352.html',
        'table5' : '/include2/timetable/352.html',
        'table6' : '/include2/timetable/352.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 9番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 10番のりば','/include/line/root_stop/imgonly2.html'],
            ['錦糸町駅','/include/line/root_stop/common.html','35.696491,139.815121','18'],
            ['両国駅入口','/include/line/root_stop/common.html','35.694596,139.796645','18'],
            ['東京スカイツリータウン 2番のりば','/include/line/root_stop/skytree.html','35.710589,139.811783','18'],
        ],
        'page_id' : 'AirportCheckHaneKinshi'
    },
    '/airport/h-soga/' : {
        'table1' : '/include2/timetable/391.html',
        'table2' : '/include/timetable/391.html',
        'table3' : '/include/timetable/391.html',
        'table4' : '/include2/timetable/391.html',
        'table5' : '/include2/timetable/391.html',
        'table6' : '/include2/timetable/391.html',
        'bus_stop' : [
          ['横浜駅（YCAT） 5番のりば','/include/line/root_stop/ycat.html'],
          ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
          ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
          ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
          ['市原駐車場','/include/line/root_stop/common.html','35.501695,140.089223','18'],
          ['五井駅東口 1番のりば','/include/line/root_stop/common.html','35.51285,140.090037','18'],
          ['蘇我駅東口 4番のりば','/include/line/root_stop/common.html','35.580932,140.13206','18'],
        ],
        'page_id' : 'AirportCheckHaneSoga'
    },
    '/airport/h-soka/' : {
        'table1' : '/include2/timetable/370.html',
        'table2' : '/include/timetable/370.html',
        'table3' : '/include/timetable/370.html',
        'table4' : '/include2/timetable/370.html',
        'table5' : '/include2/timetable/370.html',
        'table6' : '/include2/timetable/370.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['八潮駅北口 5番のりば','/include/line/root_stop/common.html','35.807511,139.843211','18'],
            ['草加駅東口 4番のりば','/include/line/root_stop/common.html','35.828307,139.803887','18'],
            ['新越谷駅西口','/include/line/root_stop/common.html','35.875286,139.789409','18'],
        ],
        'page_id' : 'AirportCheckHaneSouka'
    },
        '/airport/h-tachikawa/' : {
        'table1' : '/include2/timetable/389.html',
        'table2' : '/include/timetable/389.html',
        'table3' : '/include/timetable/389.html',
        'table4' : '/include2/timetable/389.html',
        'table5' : '/include2/timetable/389.html',
        'table6' : '/include2/timetable/389.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 9番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 10番のりば','/include/line/root_stop/imgonly2.html'],
            ['谷保駅','/include/line/root_stop/common.html','35.681649, 139.44646','18'],
            ['国立駅南口 6番のりば','/include/line/root_stop/common.html','35.698581, 139.44695','18'],
            ['立川駅北口 13番のりば','/include/line/root_stop/common.html','35.698877,139.412812','18'],
            ['SORANO HOTEL','/include/line/root_stop/common.html','35.702289,139.411523','18'],
            ['ファーレ立川','/include/line/root_stop/common.html','35.701734,139.413685','18'],
            ['昭島駅北口 1番のりば','/include/line/root_stop/common.html','35.714191,139.360844','18'],
            ['拝島操車場','/include/line/root_stop/common.html','35.713784,139.336144','18'],
        ],
        'page_id' : 'AirportCheckHaneTachikawa'
    },
    '/airport/h-tama/' : {
        'table1' : '/include2/timetable/408.html',
        'table2' : '/include/timetable/408.html',
        'table3' : '/include/timetable/408.html',
        'table4' : '/include2/timetable/408.html',
        'table5' : '/include2/timetable/408.html',
        'table6' : '/include2/timetable/408.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 11番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly2.html'],
            ['市ヶ尾駅　1番のりば','/include/line/root_stop/common.html','35.551844, 139.541648','18'],
            ['たまプラーザ駅 南口13番のりば','/include/line/root_stop/common.html','35.576866,139.558305','18'],
        ],
        'page_id' : 'AirportCheckHaneTama'
    },
    '/airport/h-tateyama/' : {
        'table1' : '/include2/timetable/404.html',
        'table2' : '/include/timetable/404.html',
        'table3' : '/include/timetable/404.html',
        'table4' : '/include2/timetable/404.html',
        'table5' : '/include2/timetable/404.html',
        'table6' : '/include2/timetable/404.html',
        'bus_stop' : [
            ['横浜駅（YCAT） 5番のりば','/include/line/root_stop/ycat.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['木更津羽鳥野バストップ','/include/line/root_stop/common.html','35.34729,139.9445','18'],
            ['君津バスターミナル 2番のりば','/include/line/root_stop/common.html','35.318561,139.935738','18'],
            ['富津浅間山バスストップ','/include/line/root_stop/common.html','35.23644963303819, 139.88796147863874','18'],
            ['ハイウェイオアシス富楽里','/include/line/root_stop/common.html','35.09999,139.8557','18'],
            ['とみうら枇杷倶楽部','/include/line/root_stop/common.html','35.03842,139.8368','18'],
            ['館山駅前','/include/line/root_stop/common.html','34.99648,139.8626','18'],
        ],
        'page_id' : 'AirportCheckHaneKimitsubus'
    },
    '/airport/h-tbigsight/' : {
        'table1' : '/include2/timetable/167.html',
        'table2' : '/include/timetable/167.html',
        'table3' : '/include/timetable/167.html',
        'table4' : '/include2/timetable/167.html',
        'table5' : '/include2/timetable/167.html',
        'table6' : '/include2/timetable/167.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 4番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['フジテレビ前','/include/line/root_stop/common.html','35.627685,139.77497','18'],
            ['グランドニッコー東京 台場 2階エントランス','/include/line/root_stop/common.html','35.625131,139.771379','18'],
            ['東京テレポート駅  5番のりば','/include/line/root_stop/common.html','35.626909,139.779769','18'],
            ['パレットタウン前','/include/line/root_stop/common.html','35.624667,139.781558','18'],
            ['東京ビッグサイト  会議棟1階バスターミナル2番のりば','/include/line/root_stop/common.html','35.630171,139.79373','18'],
        ],
        'page_id' : 'AirportCheckHaneBig'
    },
    '/airport/h-tibachuo/' : {
        'table1' : '/include2/timetable/395.html',
        'table2' : '/include/timetable/395.html',
        'table3' : '/include/timetable/395.html',
        'table4' : '/include2/timetable/395.html',
        'table5' : '/include2/timetable/395.html',
        'table6' : '/include2/timetable/395.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番（深夜6番）のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番（深夜15番）のりば','/include/line/root_stop/imgonly2.html'],
            ['ホテルスプリングス','/include/line/root_stop/common.html','35.649105,140.044108','18'],
            ['海浜幕張駅 北口3番のりば','/include/line/root_stop/common.html','35.649294,140.042307','18'],
            ['メッセ中央 幕張メッセ 中央エントランス下1階 3番のりば','/include/line/root_stop/common.html','35.647831,140.035798','18'],
            ['ホテルニューオータニ幕張','/include/line/root_stop/common.html','35.645624,140.038828','18'],
            ['ホテルフランクス','/include/line/root_stop/common.html','35.645535,140.039932','18'],
            ['ザ・マンハッタン','/include/line/root_stop/common.html','35.644955,140.040583','18'],
            ['ホテルグリーンタワー','/include/line/root_stop/common.html','35.646217,140.040324','18'],
            ['アパホテル＆リゾート＜東京ベイ幕張＞','/include/line/root_stop/common.html','35.644417,140.037058','18'],
            ['幕張ベイタウン','/include/line/root_stop/common.html','35.644827,140.047456','18'],
            ['検見川浜駅','/include/line/root_stop/common.html','35.63859,140.060222','18'],
            ['稲毛海岸駅 南口0番のりば','/include/line/root_stop/common.html','35.628762,140.072131','18'],
            ['幸町第三','/include/line/root_stop/common.html','35.616376,140.093305','18'],
            ['千葉みなと駅','/include/line/root_stop/common.html','35.609099,140.102399','18'],
            ['JR千葉駅 西口25番のりば','/include/line/root_stop/common.html','35.613,140.111577','18'],
            ['千葉中央駅 西口5番のりば ','/include/line/root_stop/common.html','35.607057,140.117771','18'],
        ],
        'page_id' : 'AirportCheckHaneMaku'
    },
    '/airport/h-tokyo/' : {
        'table1' : '/include2/timetable/324.html',
        'table2' : '/include/timetable/324.html',
        'table3' : '/include/timetable/324.html',
        'table4' : '/include2/timetable/324.html',
        'table5' : '/include2/timetable/324.html',
        'table6' : '/include2/timetable/324.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 1番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 3番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 4番のりば','/include/line/root_stop/imgonly2.html'],
            ['東京駅八重洲北口（鉄鋼ビル）鉄鋼ビル1階バスターミナル 2番のりば','/include/line/root_stop/common.html','35.682251,139.769913','18'],
        ],
        'page_id' : 'AirportCheckHaneTokyo'
    },
    '/airport/h-tsukuba/' : {
        'table1' : '/include2/timetable/153.html',
        'table2' : '/include/timetable/153.html',
        'table3' : '/include/timetable/153.html',
        'table4' : '/include2/timetable/153.html',
        'table5' : '/include2/timetable/153.html',
        'table6' : '/include2/timetable/153.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 9番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly2.html'],
            ['並木大橋','/include/line/root_stop/common.html','36.06144,140.1411','18'],
            ['並木二丁目','/include/line/root_stop/common.html','36.06417,140.137','18'],
            ['並木一丁目','/include/line/root_stop/common.html','36.069736,140.129681','18'],
            ['千現一丁目','/include/line/root_stop/common.html','36.075214,140.124982','18'],
            ['竹園二丁目','/include/line/root_stop/common.html','36.079588,140.121822','18'],
            ['つくばセンター 公共交通広場 8番のりば','/include/line/root_stop/common.html','36.0821,140.1127','18'],
        ],
        'page_id' : 'AirportCheckHaneTsukuba'
    },
    '/airport/h-yamashita/' : {
        'table1' : '/include2/timetable/364.html',
        'table2' : '/include2/timetable/365.html',
        'table3' : '/include/timetable/364.html',
        'table4' : '/include/timetable/365.html',
        'table5' : '/include2/timetable/365.html',
        'table6' : '/include/timetable/365.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 8番のりば （横浜駅(YCAT) 経由便のみ7番のりば）','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 12番のりば （横浜駅(YCAT) 経由便のみ11番のりば）','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 11番のりば （横浜駅(YCAT) 経由便のみ10番のりば）','/include/line/root_stop/imgonly1.html'],
            ['横浜駅（YCAT） 3番のりば','/include/line/root_stop/ycat.html'],
            ['横浜人形の家前','/include/line/root_stop/common.html','35.44367,139.6522','18'],
            ['山下公園前','/include/line/root_stop/common.html','35.445296,139.649645','18'],
            ['ローズホテル横浜（横浜中華街） 正面玄関','/include/line/root_stop/common.html','35.44391,139.646577','18'],
            ['新県庁前','/include/line/root_stop/common.html','35.448061,139.642233','18'],
            ['インターコンチネンタル横浜　Pier8','/include/line/root_stop/common.html','35.456416,139.642017','18'],
            ['国際橋・カップヌードルミュージアム前','/include/line/root_stop/common.html','35.455144,139.638710','18'],
            ['ヨコハマグランドインターコンチネンタルホテル（パシフィコ横浜） ホテル正面玄関','/include/line/root_stop/common.html','35.457972,139.636773','18'],
            ['横浜ベイホテル東急 正面玄関','/include/line/root_stop/common.html','35.456861,139.635443','18'],
            ['ウェスティンホテル横浜','/include/line/root_stop/common.html','35.457301,139.627230','18'], 
            ['桜木町駅 7番のりば','/include/line/root_stop/common.html','35.451503881716114, 139.63201438895544','18'],
            ['ザ・カハラ・ホテル＆リゾート横浜（パシフィコ横浜ノース）','/include/line/root_stop/common.html','35.46269,139.634126','18'],
            ['Ｋアリーナ横浜・ヒルトン横浜','/include/line/root_stop/common.html','35.464870, 139.629907','18'],
            ['馬車道駅前','/include/line/root_stop/common.html','35.45025,139.637826','18'],
            ['赤レンガ倉庫','/include/line/root_stop/common.html','35.45322,139.642','18'],
        ],
        'page_id' : 'AirportCheckHaneYamashita'
    },
      '/airport/h-yokohama/' : {
        'table1' : '/include2/timetable/393.html',
        'table2' : '/include/timetable/374.html',
        'table3' : '/include/timetable/393.html',
        'table4' : '/include2/timetable/374.html',
        'table5' : '/include2/timetable/374.html',
        'table6' : '/include2/timetable/374.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 10番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 11番のりば','/include/line/root_stop/imgonly2.html'],
            ['東新整備場','/include/line/root_stop/common.html','35.542102,139.792798','18'],
            ['南新整備場','/include/line/root_stop/common.html','35.539327,139.79466','18'],
            ['西新整備場','/include/line/root_stop/common.html','35.539529,139.793002','18'],
            ['横浜駅（YCAT） 3番のりば','/include/line/root_stop/ycat.html'],
        ],
        'page_id' : 'AirportCheckHaneYoko'
      },
    '/airport/h-yprince/' : {
        'table1' : '/include2/timetable/376.html',
        'table2' : '/include/timetable/376.html',
        'table3' : '/include/timetable/376.html',
        'table4' : '/include2/timetable/376.html',
        'table5' : '/include2/timetable/376.html',
        'table6' : '/include2/timetable/376.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 8番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 12番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 11番のりば','/include/line/root_stop/imgonly1.html'],
            ['新横浜駅 駅前バスターミナル 1番のりば','/include/line/root_stop/common.html','35.507686,139.616596','18'],
            ['新横浜プリンスホテル 正面玄関', '/include/line/root_stop/common.html', '35.510083,139.61982', '18'],
            ['センター南駅 8番のりば','/include/line/root_stop/common.html','35.545663,139.575537','18'],
            ['センター北駅 5番のりば','/include/line/root_stop/common.html','35.553447,139.577424','18'],
        ],
        'page_id' : 'AirportCheckHaneShinyoko'
    },
'/airport/n-yokohama/' : {
    'table1' : '/include/timetable/396.html',
    'table2' : '/include2/timetable/396.html',
    'table3' : '/include/timetable/396.html',
    'table4' : '/include2/timetable/396.html',
    'table5' : '/include2/timetable/396.html',
    'table6' : '/include2/timetable/396.html',
    'bus_stop' : [
        ['横浜駅（YCAT） 1番のりば','/include/line/root_stop/ycat.html'],
        ['成田空港（第1ターミナル）1階到着ロビー 12番のりば','/include/line/root_stop/common.html','35.76407,140.3866','18'],
        ['成田空港（第2ターミナル）1階到着ロビー 15番のりば','/include/line/root_stop/common.html','35.77227,140.3881','18'],
        ['成田空港（第3ターミナル） 7番のりば','/include/line/root_stop/common.html','35.777805,140.384652','18'],
        ['横浜ベイホテル東急 正面玄関【経由便のみ】','/include/line/root_stop/common.html','35.456861,139.635443','18'],
        ['ヨコハマグランドインターコンチネンタルホテル（パシフィコ横浜） ホテル正面玄関【経由便のみ】','/include/line/root_stop/common.html','35.457972,139.636773','18'],
    ],
    'page_id' : 'AirportCheckNariYoko'
},
    '/airport/h-mobara/' : {
        'table1' : '/include2/timetable/283.html',
        'table2' : '/include/timetable/283.html',
        'table3' : '/include/timetable/283.html',
        'table4' : '/include2/timetable/283.html',
        'table5' : '/include2/timetable/283.html',
        'table6' : '/include2/timetable/283.html',
        'bus_stop' : [
            ['横浜駅 東口バスターミナル18番のりば','/include/line/root_stop/yokohama.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['市原鶴舞バスターミナル','/include/line/root_stop/common.html','35.36541,140.185399','18'],
            ['長南駐車場','/include/line/root_stop/common.html','35.40639,140.2399','18'],
            ['茂原駅 南口5番のりば','/include/line/root_stop/common.html','35.42636,140.3038','18'],
        ],
        'page_id' : 'AirportCheckHaneMobara'
    },
    '/airport/h-hakuba/' : {
        'table1' : '/include2/timetable/115.html',
        'table2' : '/include/timetable/115.html',
        'table3' : '/include/timetable/115.html',
        'table4' : '/include2/timetable/115.html',
        'table5' : '/include2/timetable/115.html',
        'table6' : '/include2/timetable/115.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['五竜エスカルプラザ','/include/line/root_stop/common.html','36.6632847875179,137.83677629080614','18'],
            ['白馬五竜','/include/line/root_stop/common.html','36.65690,137.8481','18'],
            ['白馬駅','/include/line/root_stop/common.html','36.69572,137.8630','18'],
            ['白馬八方バスターミナル','/include/line/root_stop/common.html','36.70144, 137.8456','18'],
        ],
        'page_id' : 'AirportCheckHaneHakuba'
    },
    '/airport/h-osaki/' : {
        'table1' : '/include2/timetable/199.html',
        'table2' : '/include/timetable/199.html',
        'table3' : '/include/timetable/199.html',
        'table4' : '/include2/timetable/199.html',
        'table5' : '/include2/timetable/199.html',
        'table6' : '/include2/timetable/199.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 10番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly1.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 16番のりば','/include/line/root_stop/imgonly2.html'],
            ['大崎駅西口 バスターミナル1～3番のりば','/include/line/root_stop/common.html','35.61816,139.7287','18'],
        ],
        'page_id' : 'AirportCheckHaneOsaki'
    },  
    '/airport/hi-shinbashi/' : {
        'table1' : '/include/timetable/215.html',
        'table2' : '/include2/timetable/215.html',
        'table3' : '/include2/timetable/215.html',
        'table4' : '/include/timetable/215.html',
        'table5' : '/include/timetable/215.html',
        'table6' : '/include/timetable/215.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['新橋駅（銀座口）2番のりば','/include/line/root_stop/common.html','35.667134,139.758486','18'],
            ['シナガワグース EXインエントランス','/include/line/root_stop/common.html','35.63019,139.7364','18'],
            ['品川駅東口（港南口）','/include/line/root_stop/common.html','35.629584,139.742205','18'],
            ['大井町駅　西口3番のりば','/include/line/root_stop/common.html','35.606658,139.734375','18'],
        ],
        'page_id' : 'AirportCheckHaneKokuShinbashi'
    },
    '/airport/h-yokohama/index_lift.html' : {
        'table1' : '/include/timetable/146.html',
        'table2' : '/include2/timetable/146.html',
        'table3' : '/include2/timetable/146.html',
        'table4' : '/include/timetable/146.html',
        'table5' : '/include/timetable/146.html',
        'table6' : '/include/timetable/146.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 0番のりば（リフト付きリムジンバス専用）','/include/line/root_stop/imgonly3.html'],
            ['横浜駅（YCAT） 4番のりば(リフト付きリムジンバス専用)','/include/line/root_stop/ycat.html'],
        ],
        'page_id' : 'AirportCheckHaneYokoLift'
    },
    '/airport/h-matsudo/' : {
        'table1' : '/include/timetable/330.html',
        'table2' : '/include2/timetable/330.html',
        'table3' : '/include2/timetable/330.html',
        'table4' : '/include/timetable/330.html',
        'table5' : '/include/timetable/330.html',
        'table6' : '/include/timetable/330.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 6番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 15番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly1.html'],
            ['松戸駅西口　9番のりば','/include/line/root_stop/common.html','35.784547,139.899417','18'],
            ['新松戸駅　3番のりば','/include/line/root_stop/common.html','35.825335,139.920233','18'],
        ],
        'page_id' : 'AirportCheckHaneMatsudo'
    },
    '/airport/h-mitsuikisarazu/' : {
        'table1' : '/include/timetable/359.html',
        'table2' : '/include2/timetable/359.html',
        'table3' : '/include2/timetable/359.html',
        'table4' : '/include/timetable/359.html',
        'table5' : '/include/timetable/359.html',
        'table6' : '/include/timetable/359.html',
        'bus_stop' : [
            ['羽田空港第3ターミナル 7番のりば','/include/line/root_stop/imgonly0.html'],
            ['羽田空港第2ターミナル 1階到着ロビー 14番のりば','/include/line/root_stop/imgonly2.html'],
            ['羽田空港第1ターミナル 1階到着ロビー 13番のりば','/include/line/root_stop/imgonly1.html'],
            ['三井アウトレット木更津　1番のりば','/include/line/root_stop/common.html','35.4345,139.9379','18'],
        ],
        'page_id' : 'AirportCheckHaneMitsuiKisarazu'
    },
    '/line/root_stop/yokosuka_shiokaze.html' : {
        'table1' : '/include2/timetable/272.html',
        'table2' : '/include/timetable/272.html',
        'table3' : '/include/timetable/272.html',
        'table4' : '/include2/timetable/272.html',
        'table5' : '/include2/timetable/272.html',
        'table6' : '/include2/timetable/272.html',
        'bus_stop' : [
            ['横須賀駅 3番のりば','/include/line/root_stop/common.html','35.2844991937275,139.656368477944','18'],
            ['汐留','/include/line/root_stop/common.html','35.2818728808623,139.662510752677','18'],
            ['観音崎京急ホテル・横須賀美術館前','/include/line/root_stop/common.html','35.2608874810751,139.7376693477','18'],
            ['ドック前','/include/line/root_stop/common.html','35.2445626005368,139.716315185706','18'],
            ['燈明堂入口','/include/line/root_stop/common.html','35.2340938924622,139.721805035908','18'],
            ['ドック前','/include/line/root_stop/common.html','35.244496884003,139.715939676444','18'],
            ['観音崎京急ホテル・横須賀美術館前','/include/line/root_stop/common.html','35.2609389486236,139.737108095554','18'],
            ['汐留','/include/line/root_stop/common.html','35.2826282692797,139.659179449081','18'],
        ],
        'page_id' : 'BusYokosukaShiokaze'
    },
}

// IE対応
if (!String.prototype.startsWith) {
    String.prototype.startsWith = function(searchString, position){
      position = position || 0;
      return this.substr(position, searchString.length) === searchString;
  };
}
// 20200522 時刻表を暫定で表示しない
var ignoreList = ['/airport/hi-omori/', '/airport/hi-kamata/', '/airport/h-kisarazu/', '/airport/h-tateyama/', '/airport/h-funabashi/', '/airport/h-tama/', '/airport/h-mkosugi/', '/airport/h-kasiwanishi/', '/airport/h-fujimino/', '/airport/h-katsunuma/', '/airport/h-yokohama/', '/airport/n-yokohama/','/airport/h-yprince/','/airport/h-soga/','/airport/h-oimachi/','/line/root_stop/yokosuka_shiokaze.html','/airport/h-honatsugi/','/airport/h-futamata/','/airport/h-kimitsu/','/airport/h-kitasenjyu/','/airport/h-mobara/','/airport/h-soka/','/airport/h-machida/','/airport/h-yamashita/','/airport/h-nikotama/','/airport/h-shinyuri/','/airport/h-kichijyoji/','/airport/h-skytree/','/airport/h-mitsuikisarazu/','/airport/h-gotenba/','/airport/h-shibuya/','/airport/h-disney/','/airport/h-kawaguchi/','/airport/h-tibachuo/','/airport/h-kawaguhiko/','/airport/h-tokyo/','/airport/h-hakuba/','/airport/hi-mm/','/airport/h-tachikawa/'];
for (var key in fileName) {
    if (ignoreList.indexOf(key) !== -1) {
        continue;
    }
    for (var key2 in fileName[key] ) {
        if (key2.startsWith('table')) {
            delete fileName[key][key2];
        }
    }
}

var tab_index = 0;
var tab_index2 = 0;
var is_exist_tab = 0;

// 時刻表の読み込み
$(window).on("load", function () {
    for (var i = 1; i <= 6; i++) {
        $('.airport-table'+i).load(fileName[page]["table"+i],null,function(){
            set_top_margin();
        });
    };

    $('.tab ul li').click(function () {
        var index = $('.tab ul li').index(this);
        $('.tab-cont .section').css('display', 'none');
        $('.tab-cont .section').eq(index).css('display', 'block');
        $('.tab-cont .section').addClass('hide');
        $('.tab-cont .section').eq(index).removeClass('hide');
        $('.tab ul li').removeClass('select');
        $(this).addClass('select');
        set_top_margin();
        tab_index = index;
    });
    $('.tab2 ul li').click(function () {
        var index = $('.tab2 ul li').index(this);
        $('.tab-cont2 .section').css('display', 'none');
        $('.tab-cont2 .section').eq(index).css('display', 'block');
        $('.tab-cont2 .section').addClass('hide');
        $('.tab-cont2 .section').eq(index).removeClass('hide');
        $('.tab2 ul li').removeClass('select');
        $(this).addClass('select');
        set_top_margin();
        tab_index2 = index;
    });

    is_exist_tab = $('#tab1')[0] ? 1:0;
});

// リサイズ時のマージン調整
$(window).on("resize", function () {
    set_top_margin();

    var windowWidth = $(window).width();
    var windowSm = 640;

    if(windowWidth >= windowSm){
        $('table[class*=t-ttl]').each(function() {
            $(this).css("top", '');
        });
    }
});

// 時刻表のヘッダーとの位置調整
function set_top_margin(table_num){
    var windowWidth = $(window).width();
    var windowSm = 640;

    if(windowWidth <= windowSm){
        // スマホ画面の場合
        var timetable = table_num === undefined ? $('[id^=timetable]') : $('#timetable'+table_num);
        timetable.each(function() {
            var title_height = $(this).children('table[class*=t-ttl]').height();
            $(this).children('div.common-table-wrap').css("margin-top", title_height);
        });
    }else{
        // PC画面の場合
        var timetable = $('[id^=timetable]');
        timetable.each(function() {
            $(this).children('div.common-table-wrap').css("margin-top", '');
        });
    }
}

// 時刻表ヘッダー追従
$(window).on("scroll", function () {
    var windowWidth = $(window).width();
    var windowSm = 640;
    if(windowWidth >= windowSm){ return } // PC表示の場合は処理しない

    var title_table;
    var margin_top;
    var window_top =  $(window).scrollTop();


    var time_table1 = is_exist_tab ? $(".tab-cont.common-tab-box2").find('[id^=timetable]:visible') : $("#timetable1");
    if (!time_table1.length){ return } // timetableが非表示の場合は処理しない
    var start_postion1 = time_table1.offset().top;
    var stop_position1 = time_table1.offset().top + time_table1.height() - time_table1.children('[class*=t-ttl]').height();

    var time_table2 = is_exist_tab ? $(".tab-cont2.common-tab-box2").find('[id^=timetable]:visible') : $("#timetable2");
    if (!time_table2.length){ return } // timetableが非表示の場合は処理しない
    var start_postion2 = time_table2.offset().top;
    var stop_position2 = time_table2.offset().top + time_table2.height() - time_table2.children('[class*=t-ttl]').height();

    if( window_top >= start_postion1 && window_top <= stop_position1 ){
        title_table = time_table1.children('[class*=t-ttl]');
        margin_top = window_top - start_postion1 ;
        title_table.animate({"top": margin_top},{duration:0,queue:false});
    }else{
        time_table1.children('[class*=t-ttl]').css('top', '');
    }

    if( window_top >= start_postion2 && window_top <= stop_position2 ){
        title_table = time_table2.children('[class*=t-ttl]');
        margin_top = window_top - start_postion2 ;
        title_table.animate({"top": margin_top},{duration:0,queue:false});
    }else{
        time_table2.children('[class*=t-ttl]').css('top', '');
    }
});

Error.prepareStackTrace = function( e, st ) {
  return {
    functionName: st[0].getFunctionName(),
    lineNumber: st[0].getLineNumber(),
  };
};
function log( msg ) {
  var obj = {};
  Error.captureStackTrace( obj, log );
  console.log( msg + " at " + obj.stack.lineNumber );
}

$(function () {
    $("#news-airport").load('/topics_info/index.html #posts_home',null, function() {
        var target = 'li.'+fileName[page].page_id;
        $('#posts_home').show();
        $('#posts_home').find('li').hide();
        $('#posts_home').find(target).show();
    });

    var _ua = (function(){
      return {
        ltIE6:typeof window.addEventListener == "undefined" && typeof document.documentElement.style.maxHeight == "undefined",
        ltIE7:typeof window.addEventListener == "undefined" && typeof document.querySelectorAll == "undefined",
        ltIE8:typeof window.addEventListener == "undefined" && typeof document.getElementsByClassName == "undefined",
        ltIE9:document.uniqueID && typeof window.matchMedia == "undefined",
        gtIE10:document.uniqueID && window.matchMedia,
        Trident:document.uniqueID,
        Gecko:'MozAppearance' in document.documentElement.style,
        Presto:window.opera,
        Blink:window.chrome,
        Webkit:typeof window.chrome == "undefined" && 'WebkitAppearance' in document.documentElement.style,
        Touch:typeof document.ontouchstart != "undefined",
        Mobile:typeof window.orientation != "undefined",
        ltAd4_4:typeof window.orientation != "undefined" && typeof(EventSource) == "undefined",
        Pointer:window.navigator.pointerEnabled,
        MSPoniter:window.navigator.msPointerEnabled
      }
    })();

    var page_data = fileName[page];
    $.each(page_data.bus_stop, function(index, data){
      var element_num = index + 1;
      if(data != undefined){
          $('#airport-pulldown' + element_num).load(data[1],null,function(){
              $('#airport-pulldown' + element_num + ' .sub2-ttl').html(data[0].replace(/R」/,'&#xae」') + '<span><em>非</em>表示</span>');
              var file_id = data[1].replace(/(.*root_stop\/)(.*)(\.html)/,'$2');
              if(
                  file_id === 'common' ||
                  file_id.match(/imgonly/) || file_id.match(/shibuya/) ||
                  file_id === 'skytree'
              ){
                  var name = data[0];
                  var lat_lon = data[2];
                  var zoom = data[3];
                  var ifmSrc;
                  if(!data[4]){
                      ifmSrc = 'https://maps.google.co.jp/maps?ll='+ lat_lon +'&q='+ lat_lon +'&output=embed&t=m&z='+ zoom;
                  }else{
                      ifmSrc = 'https://maps.google.co.jp/maps?ll='+ lat_lon +'&output=embed&t=m&z='+ zoom;
                  }
                  if(!file_id.match(/imgonly/)){
                      $('#airport-pulldown' + element_num + ' #ifm')[0].contentDocument.location.replace(ifmSrc);
                      if(_ua.Trident && !_ua.ltIE8 && !_ua.gtIE10){
                          // for IE9
                          var appendStr = '<a href="https://maps.google.co.jp/maps?&ll='+ lat_lon +'&q='+ lat_lon +'&z='+ '20' +'" target="_blank" class="blank">こちらからご確認ください</a>';
                          $(this).find('.ggmap').parent().append(appendStr);
                          $(this).find('.ggmap').remove();
                      }
                  }
              }
        
             $("#airport-pulldown" + element_num + " .include-one-marker dt, #airport-pulldown" + element_num + " .highway-pulldown.include-multi-marker dt, #airport-pulldown" + element_num + " .highway-pulldown.include-one-marker dt , #airport-pulldown" + element_num + " .include-multi-marker dt").on("click", function () {
                var $dd = $(this).next("dd");
                
                if ($dd.css("display") === "block") {
                    $dd.css("display", "none");
                    
                } else {
                    $dd.slideToggle(0);
                    
                }
                $(this).toggleClass("on");
            });
        
            
        

          });
      }
    });

});
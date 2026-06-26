var Advancedname = ""; //高级检索中文表达式
var userInfo = {}; // 需要先调用checkLogin() 判断登陆成功了才会有值
var pageType = getUrlParam("pageType") === null || getUrlParam("pageType") === "" ? 1 : 2;
var languageDataLoaded = true; // 判断高级检索外文图书语种请求
$(function () {
    //自动完成
    //$("#text_search").focus(function () {
    //    if ($(this).val() == "请输入关键词") {
    //        $(this).val("");
    //    }
    //});

    $(".search-type li").click(function () {
        if ($(this).attr("data-val") != $("#hidSearchType").val()) {
            $("#hidSearchType").val($(this).attr("data-val"));
            $(".search-type li.zx-current").removeClass("zx-current");
            $(this).addClass("zx-current");
            //auto($("#text_search"));
            if ($(this).attr("data-val") == "1") {
                $("#QKDH").show();
            } else {
                $("#QKDH").hide();
            }

            if ($("#hidSearchType").val() == "1") {
                $(".searchField").text("刊名");
                $("#select_type").val('TS');
            } else if ($("#hidSearchType").val() == "5") {
                $(".searchField").text("题名");
                $("#select_type").val('IKTE');
            } else if ($("#hidSearchType").val() == "2") {
                $(".searchField").text("书名");
                $("#select_type").val('IKTE');
            } else if ($("#hidSearchType").val() == "7") {
                $(".searchField").text("刊名");
                $("#select_type").val('TS');
            } else if ($("#hidSearchType").val() == "8") {
                $(".searchField").text("书名");
                $("#select_type").val('name');
            } else {
                $(".searchField").text("题名/关键词");
                $("#select_type").val('TS');
            }
        }
    });

    $("#listclassdiv a").click(function () {
        if ($(this).attr("class") == "show") {
            $(this).attr("class", "hide");
            $(this).parent().parent().find("div").show();
        } else {
            $(this).attr("class", "show");
            $(this).parent().parent().find("div").hide();
        }
    });

    $("#listclassdiv input[type=checkbox]").click(function () {
        if ($(this).prop("checked") == true) {
            if ($(this).attr("level") == 1) {
                var classname = $(this).prop("name");
                var ischeck = $(this).prop("checked");
                $("#listclassdiv input[name='" + classname + "'][level=2]").each(function () {
                    $(this).prop("checked", !ischeck);
                });
            }
            if ($(this).attr("level") == 2) {
                var classname = $(this).prop("name");
                var ischeck = $(this).prop("checked");
                $("#listclassdiv input[name='" + classname + "'][level=1]").each(function () {
                    $(this).prop("checked", !ischeck);
                });
            }
        }
    });
    //外文图书
    $("#listtsclassdiv a").click(function () {
        if ($(this).attr("class") == "show") {
            $(this).attr("class", "hide");
            $(this).parent().parent().find("div").show();
        } else {
            $(this).attr("class", "show");
            $(this).parent().parent().find("div").hide();
        }
    });

    $("#listtsclassdiv input[type=checkbox]").click(function () {
        if ($(this).prop("checked") == true) {
            if ($(this).attr("level") == 1) {
                var classname = $(this).prop("name");
                var ischeck = $(this).prop("checked");
                $("#listtsclassdiv input[name='" + classname + "'][level=2]").each(function () {
                    $(this).prop("checked", !ischeck);
                });
            }
            if ($(this).attr("level") == 2) {
                var classname = $(this).prop("name");
                var ischeck = $(this).prop("checked");
                $("#listtsclassdiv input[name='" + classname + "'][level=1]").each(function () {
                    $(this).prop("checked", !ischeck);
                });
            }
        }
    });

    searchInit();
    //搜索栏自动补全功能
    //auto($("#text_search"));
    //下拉框绑定change事件
    //layui.use('form', function () {
    //    var form = layui.form();
    //    form.on('select(aihao)', function () {
    //        auto($("#text_search"));
    //    });
    //});
});
$(window).load(function () {
    $(".search-type li").each(function () {
        if ($(this).attr("class") == "zx-current") {
            if ($(this).attr("data-val") == "1") {
                $("#QKDH").show();
            }
        }
    });
    $("#text_search").bind("keydown", function (e) {
        // 兼容FF和IE和Opera
        var theEvent = e || window.event;
        var code = theEvent.keyCode || theEvent.which || theEvent.charCode;
        if (code == 13) {
            //回车执行查询
            $("#but_search").click();
        }
    });
    $("#text_search_xuexi").bind("keydown", function (e) {
        // 兼容FF和IE和Opera
        var theEvent = e || window.event;
        var code = theEvent.keyCode || theEvent.which || theEvent.charCode;
        if (code == 13) {
            //回车执行查询
            $("#but_search_xuexi").click();
        }
    });
});
//搜索栏自动补全功能
//function auto(obj) {
//    obj.autocomplete({
//        // 静态的数据源，根据label属性进行显示或模糊匹配，当给输入框设置value属性值
//        source: "/Ajax/SeachHandler.ashx?method=getautocomplete&field=" + $("#select_type").val() + "&Type=" + $("#hidSearchType").val(),//ajax动态获取数据
//        //focus: function (event, ui) {
//        //    $("#txtContent").val(ui.item.title);
//        //    return false;
//        //},

//        select: function (event, ui) {
//            $("#text_search").val(ui.item.Key);
//            return false;
//        }
//    }).data("ui-autocomplete")._renderItem = function (ul, item) { //添加自定义元素到自动补全栏中
//        return $("<li>").append("<a title='" + item.Key + "'>" + (item.Key.length > 15 ? item.Key.substring(0, 15) + "..." : item.Key) + "</a>").appendTo(ul);
//    };
//}

//获取url中的参数
function getUrlParam(name) {
    var reg = new RegExp("(^|&)" + name + "=([^&]*)(&|$)"); //构造一个含有目标参数的正则表达式对象
    var r = window.location.search.substr(1).match(reg); //匹配目标参数
    if (r != null) return decodeURI(r[2]);
    return null; //返回参数值
}

function searchInit() {
    var path = location.href;
    var cop = $("#templateCop").val();
    if (path.indexOf("/journal/") > 0) {
        if (cop === "collections") {
            $("#hidSearchType").val("7");
        } else {
            $("#hidSearchType").val("1");
        }
    } else if (path.indexOf("/Collections") > 0) {
        $("#hidSearchType").val("7");
    } else if (path.indexOf("/WaiWenBooks/") > 0) {
        $("#hidSearchType").val("8");
    }
    var type = $.trim(getUrlParam("type"));
    if (type == "Ancient") {
        //古籍
        $("#hidSearchType").val("5");
    }
    var synUpdateType = $("#templatePageType").val();
    if (synUpdateType == "2") {
        $("#hidSearchType").val("6");
    }
    $(".search-type li").each(function () {
        if ($(this).attr("data-val") == $("#hidSearchType").val()) {

            if ($("#hidSearchType").val() == "1") {
                $(".searchField").text("刊名");
                $("#select_type").val('TS');
                $(".search-type li.zx-current").removeClass("zx-current");
                $(".search-type li[data-lang='" + filterXSS($("#hidSearchValue").val()) + "']").addClass("zx-current");
                return false;
            } else {
                if ($("#hidSearchType").val() == "5") {
                    $(".searchField").text("题名");
                    $("#select_type").val('IKTE');
                } else if ($("#hidSearchType").val() == "2") {
                    $(".searchField").text("书名");
                    $("#select_type").val('IKTE');
                } else if ($("#hidSearchType").val() == "7") {
                    $(".searchField").text("刊名");
                    $("#select_type").val('TS');
                } else if ($("#hidSearchType").val() == "8") {
                    $(".searchField").text("书名");
                    $("#select_type").val('name');
                } else {
                    $(".searchField").text("题名/关键词");
                    $("#select_type").val('TS');
                }

                $(".search-type li.zx-current").removeClass("zx-current");
                $(this).addClass("zx-current");
                return false;
            }
        } else {
            $(".search-type li.zx-current").removeClass("zx-current");
            $(".search-type li").eq(0).addClass("zx-current");
        }
    });
}

//基本检索
function Basicsearch() {
    var temp = $("#select_type").val();
    var type = $("#hidSearchType").val();
    var text = type == '8' ? $("#text_search").val() || $("#text_search_xuexi").val() :
        addEscape($("#text_search").val()) || addEscape($("#text_search_xuexi").val());
    var search = "";
    var searchname = "";
    var ajaxKeys = "";
    if (text && text.length > 0) {
        if (type == "5") {
            if (temp == "IKTE") {
                search += "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\")";
                searchname += "题名=" + text;
            }
            if (temp == "BDNM") {
                search += "BDNM=\"" + text + "\"";
                searchname += "条码号=" + text;
            }
            if (temp == "IKCR") {
                search += "IKCR=\"" + text + "\"";
                searchname += "责任者=" + text;
            }
            if (temp == "IKTS") {
                search += "IKTS=\"" + text + "\"";
                searchname += "出版者=" + text;
            }
            if (temp == "ISBN") {
                search += "ISBN=*" + text + "*";
                searchname += "索书号=" + text;
            }
        } else if (type == "6") {
            if (temp == "TS") {
                search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\"  OR IKST=\"" + text + "\" OR IKET=\"" + text + "\" OR IKSE=\"" + text + "\")";
                searchname = "题名/关键词=\"" + text + "\"";
            } else if (temp == "TITE") {
                search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\" OR IKET=\"" + text + "\")";
                searchname = "题名=\"" + text + "\"";
            } else if (temp == "CRTR") {
                search = "((IKCR=" + text + " OR IKCE=" + text + ")" + " AND ik_creator:\"" + text + "\"^20) OR (IKCRE=\"" + text + "\")";
                searchname = "作者=\"" + text + "\"";
            } else if (temp == "IKST") {
                search = "(IKST=\"" + text + "\" OR IKSE=\"" + text + "\")";
                searchname = "关键词=\"" + text + "\"";
            } else if (temp == "ISSN") {
                search = "ISSN=*" + text + "*";
                searchname = "ISSN=\"" + text + "\"";
            } else if (temp == "CNEM") {
                search = "(CNEM=*" + text + "*" + " OR CNEME=" + text + ")";
                searchname = "刊名=\"" + text + "\"";
            }
            ajaxKeys = text;
        } else if (type == "2") {
            if (temp == "IKTE") {
                search += "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\")";
                searchname += "书名=" + text;
            }
            if (temp == "BDNM") {
                search += "BDNM=\"" + text + "\"";
                searchname += "条码号=" + text;
            }
            if (temp == "IKCR") {
                search += "IKCR=\"" + text + "\"";
                searchname += "著者=" + text;
            }
            if (temp == "TSPS") {
                search += "TSPS=\"" + text + "\"";
                searchname += "出版社=" + text;
            }
            if (temp == "ISBN") {
                search += "ISBN=\"" + text + "\"";
                searchname += "索书号=" + text;
            }
        } else if (type == "7") {
            if (temp == "TS") {
                search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\"  OR IKST=\"" + text + "\" OR IKET=\"" + text + "\" OR IKSE=\"" + text + "\")";
                searchname = "题名/关键词=\"" + text + "\"";
            } else if (temp == "TITE") {
                search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\" OR IKET=\"" + text + "\")";
                searchname = "题名=\"" + text + "\"";
            } else if (temp == "CRTR") {
                search = "((IKCR=" + text + " OR IKCE=" + text + ")" + " AND ik_creator:\"" + text + "\"^20)";
                searchname = "作者=\"" + text + "\"";
            } else if (temp == "IKST") {
                search = "(IKST=\"" + text + "\" OR IKSE=\"" + text + "\")";
                searchname = "关键词=\"" + text + "\"";
            } else if (temp == "ISSN") {
                search = "ISSN=*" + text + "*";
                searchname = "ISBN=\"" + text + "\"";
            }
            ajaxKeys = text;
        } else if (type == "8") {
            if (temp == "name") {
                search += "name=" + text;
                searchname += "书名=" + text;
            }
            if (temp == "zuoZhe") {
                search += "zuoZhe=" + text + "";
                searchname += "作者=" + text;
            }
            if (temp == "ChuBanShe") {
                search += "ChuBanShe=" + text + "";
                searchname += "出版社=" + text;
            }
            if (temp == "IS") {
                search += "IS=" + text + "";
                searchname += "eISBN=" + text;
            }
        } else {
            if (temp == "TS") {
                search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\"  OR IKST=\"" + text + "\" OR IKET=\"" + text + "\" OR IKSE=\"" + text + "\")";
                searchname = "题名/关键词=\"" + text + "\"";
            } else if (temp == "TITE") {
                search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\" OR IKET=\"" + text + "\")";
                searchname = "题名=\"" + text + "\"";
            } else if (temp == "CRTR") {
                search = "((IKCR=" + text + " OR IKCE=" + text + ")" + " AND ik_creator:\"" + text + "\"^20) OR (IKCRE=\"" + text + "\")";
                searchname = "作者=\"" + text + "\"";
            } else if (temp == "IKST") {
                search = "(IKST=\"" + text + "\" OR IKSE=\"" + text + "\")";
                searchname = "关键词=\"" + text + "\"";
            } else if (temp == "ISSN") {
                search = "ISSN=*" + text + "*";
                searchname = "ISSN=\"" + text + "\"";
            }
            ajaxKeys = text;
        }
        $("#text_search").val("");
        switch (type) {
            case "0": //全部文献
                if (search.length > 0) {
                    if (AntiSqlValid(search) == true) {
                        search = $.base64.encode(search, 'utf8');
                        searchname = $.base64.encode(searchname, 'utf8');
                        var url = "/Literature/articlelist?sType=0&search=" + search + "&searchname=" + searchname + "&nav=" + type
                        if (ajaxKeys) {
                            ajaxKeys = $.base64.encode(ajaxKeys, 'utf8');
                            url += "&ajaxKeys=" + ajaxKeys
                        }
                        // window.location.href = "/Literature/articlelist?search=" + search + "&searchname=" + searchname + "&nav=" + type;
                        window.open(filterXSS(url));
                        // window.event.returnValue=false;
                    }
                }
                break;
            case "1": //期刊
                if (text) {
                    var languagetype = $("#hidSearchValue").val();
                    if (!languagetype) {
                        languagetype = 1;
                    }
                    if (temp == "TS") {
                        if (AntiSqlValid(text) == true) {
                            window.open(filterXSS("/journal/list?e=s%3D" + encodeURIComponent(text) + "&langType=" + languagetype + "&keyword=" + encodeURI(text)));
                        }
                    } else {
                        search = "h=core:_" + temp + ":" + text;
                        if (AntiSqlValid(search) == true) {
                            window.open(filterXSS("/journal/list?e=" + encodeURIComponent(search) + "&langType=" + languagetype + "&keyword=" + encodeURI(text)));
                        }
                    }
                }
                break;
            case "2": //外文图书
                if (search.length > 0) {
                    if (AntiSqlValid(search) == true) {
                        search = search + " AND TYPE=外文图书 "
                        search = $.base64.encode(search, 'utf8');
                        searchname = $.base64.encode(searchname, 'utf8');
                        window.open(filterXSS("/Literature/foreignbooklist?search=" + search + "&searchname=" + searchname + "&nav=" + type));
                    }
                }
                break;
            case "3": //学位论文
                if (search.length > 0) {
                    if (AntiSqlValid(search) == true) {
                        search = search + " AND TYPE=学位论文 "
                        search = $.base64.encode(search, 'utf8');
                        searchname = $.base64.encode(searchname, 'utf8');
                        window.open(filterXSS("/Literature/articlelist?search=" + search + "&searchname=" + searchname + "&nav=" + type));
                    }
                }
                break;
            case "4": //会议论文
                if (search.length > 0) {
                    if (AntiSqlValid(search) == true) {
                        search = search + " AND TYPE=会议论文 "
                        search = $.base64.encode(search, 'utf8');
                        searchname = $.base64.encode(searchname, 'utf8');
                        window.open(filterXSS("/Literature/articlelist?search=" + search + "&searchname=" + searchname + "&nav=" + type));
                    }
                }
                break;
            case "5": //古籍
                if (search.length > 0) {
                    if (AntiSqlValid(search) == true) {
                        search = search + " AND TYPE=古籍 "
                        search = $.base64.encode(search, 'utf8');
                        searchname = $.base64.encode(searchname, 'utf8');
                        window.open(filterXSS("/Literature/ancientbooklistNew?search=" + search + "&searchname=" + searchname + "&nav=" + type + "&keyword=" + text));
                    }
                }
                break;
            case "6": //优先发布
                if (search.length > 0) {
                    if (AntiSqlValid(search) == true) {
                        search = $.base64.encode(search, 'utf8');
                        searchname = $.base64.encode(searchname, 'utf8');
                        var url = "/Literature/prplist?sType=0&search=" + search + "&searchname=" + searchname + "&nav=" + type + "&synUpdateType=2"
                        if (ajaxKeys) {
                            ajaxKeys = $.base64.encode(ajaxKeys, 'utf8');
                            url += "&ajaxKeys=" + ajaxKeys
                        }
                        window.open(filterXSS(url));
                    }
                }
                break;
            case "7"://集刊
                if (text) {
                    var languagetype = 1
                    if (temp == "TS") {
                        if (AntiSqlValid(text) == true) {
                            window.open(filterXSS("/Collections/list?e=s%3D" + encodeURIComponent(text) + "&langType=" + languagetype + "&keyword=" + encodeURI(text)));
                        }
                    } else {
                        search = "h=core:_" + temp + ":" + text;
                        if (AntiSqlValid(search) == true) {
                            window.open(filterXSS("/Collections/list?e=" + encodeURIComponent(search) + "&langType=" + languagetype + "&keyword=" + encodeURI(text)));
                        }
                    }
                }
                break;
            case "8"://外文期刊
                if (searchname && search) {
                    searchname = $.base64.encode(searchname, 'utf8');
                    search = $.base64.encode(search, 'utf8');
                    window.open(filterXSS("/ForeignBooks/getForeignBookQueryUrl?searchname=" + searchname + "&search=" + search));
                }
                break;
            case "9"://数据库连接
                break;
        }
    } else {
        layer.msg("检索条件不能为空！", {offset: 300});
    }
}

// 全部文献高级检索
function AdvancedSearch() {
    var search = ""; //拼接完后的查询表达式
    var searchname = "";
    var type = ""; //资源类型
    var type_2 = "";
    var RA = ""; //期刊类型
    var language = ""; //语言
    var CLAS = "" //分类
    var ajaxKeys = ""; //检索词
    var type_navyx = $("#hidSearchType").val();
    if ($("#u_txt_1").val().length > 0) {
        var text = addEscape($("#u_txt_1").val());
        search += selectwhere($("#u_select2_1").val(), text, $("#u_select1_1").val());
        searchname += Advancedname;
        ajaxKeys += text
    }
    if ($("#u_txt_2").val().length > 0) {
        var text = addEscape($("#u_txt_2").val());
        if (search.length > 0) {
            search += " " + $("#u_select3_2").val() + " " + selectwhere($("#u_select2_2").val(), text, $("#u_select1_2").val());
            searchname += " " + $("#u_select3_2").find("option:selected").text() + " " + Advancedname;
            ajaxKeys += ',' + text;
        } else {
            search += selectwhere($("#u_select2_2").val(), text, $("#u_select1_2").val());
            searchname += Advancedname;
            ajaxKeys += text;
        }
    }
    if ($("#u_txt_3").val().length > 0) {
        var text = addEscape($("#u_txt_3").val());
        if (search.length > 0) {
            search += " " + $("#u_select3_3").val() + " " + selectwhere($("#u_select2_3").val(), text, $("#u_select1_3").val());
            searchname += " " + $("#u_select3_3").find("option:selected").text() + " " + Advancedname;
            ajaxKeys += ',' + text;
        } else {
            search += selectwhere($("#u_select2_3").val(), text, $("#u_select1_3").val());
            searchname += Advancedname;
            ajaxKeys += text;
        }
    }
    if ($("#u_txt_4").val().length > 0) {
        var text = addEscape($("#u_txt_4").val());
        if (search.length > 0) {
            search += " " + $("#u_select3_4").val() + " " + selectwhere($("#u_select2_4").val(), text, $("#u_select1_4").val());
            searchname += " " + $("#u_select3_4").find("option:selected").text() + " " + Advancedname;
            ajaxKeys += ',' + text;
        } else {
            search += selectwhere($("#u_select2_4").val(), text, $("#u_select1_4").val());
            searchname += Advancedname;
            ajaxKeys += text;
        }
    }
    if ($("#u_txt_5").val().length > 0) {
        var text = addEscape($("#u_txt_5").val());
        if (search.length > 0) {
            search += " " + $("#u_select3_5").val() + " " + selectwhere($("#u_select2_5").val(), text, $("#u_select1_5").val());
            searchname += " " + $("#u_select3_5").find("option:selected").text() + " " + Advancedname;
            ajaxKeys += ',' + text;
        } else {
            search += selectwhere($("#u_select2_5").val(), text, $("#u_select1_5").val());
            searchname += Advancedname;
            ajaxKeys += text;
        }
    }
    if (search.length > 0) {
        search = "(" + search + ")"
    }
    if ($("#date_start").val().length > 0) {
        if (type_navyx != 6) {
            var time1 = new Date($("#date_start").val());
            if ($("#date_end").val().length > 0) {
                var time2 = new Date($("#date_end").val());
                if (search.length > 0) {
                    search += " AND years:[" + time1.format("yyyy") + " TO " + time2.format("yyyy") + "]";
                    searchname += " 且 时间=" + time1.format("yyyy-MM-dd") + " 至 " + time2.format("yyyy-MM-dd");
                } else {
                    search += " years:[" + time1.format("yyyy") + " TO " + time2.format("yyyy") + "]";
                    searchname += " 时间=" + time1.format("yyyy-MM-dd") + " 至 " + time2.format("yyyy-MM-dd");
                }

            } else {
                if (search.length > 0) {
                    search += " AND years:[" + time1.format("yyyy") + " TO * ]";
                    searchname += " 且 时间=" + time1.format("yyyy-MM-dd") + " 至今";
                } else {
                    search += " years:[" + time1.format("yyyy") + " TO * ]";
                    searchname += "时间=" + time1.format("yyyy-MM-dd") + " 至今";
                }
            }
        } else if (type_navyx == 6) {
            var time1 = new Date($("#date_start").val());
            if ($("#date_end").val().length > 0) {
                var time2 = new Date($("#date_end").val());
                var jieshushijian = ""
                if (+time2.format("MM") > 11) {
                    jieshushijian = +time2.format("yyyy") + 1 + "-01-01T00:00:00Z"
                } else {
                    var yue = +time2.format("MM") + 1
                    jieshushijian = time2.format("yyyy") + "-" + yue + "-01T00:00:00Z"
                }
                if (search.length > 0) {
                    search += " AND publishDateTime:[" + time1.format("yyyy-MM") + "-01T00:00:00Z" + " TO " + jieshushijian + "]";
                    searchname += " 且 时间=" + time1.format("yyyy-MM") + " 至 " + time2.format("yyyy-MM");
                } else {
                    search += " publishDateTime:[" + time1.format("yyyy-MM") + "-01T00:00:00Z" + " TO " + jieshushijian + "]";
                    searchname += " 时间=" + time1.format("yyyy-MM") + " 至 " + time2.format("yyyy-MM");
                }

            } else {
                if (search.length > 0) {
                    search += " AND publishDateTime:[" + time1.format("yyyy-MM") + "-01T00:00:00Z" + " TO * ]";
                    searchname += " 且 时间=" + time1.format("yyyy-MM") + " 至今";
                } else {
                    search += " publishDateTime:[" + time1.format("yyyy-MM") + "-01T00:00:00Z" + " TO * ]";
                    searchname += "时间=" + time1.format("yyyy-MM") + " 至今";
                }

            }
        }
    }
    if ($("#p_zy").find("input[type='checkbox']:checked").length > 0) {
        type_2 = "";
        for (var i = 0; i < $("#p_zy").find("input[type='checkbox']:checked").length; i++) {
            var temp = $($("#p_zy").find("input[type='checkbox']:checked")[i]).val();
            if (temp == "全部") {
                if (search.length > 0) {
                    search += " AND (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\" OR TYPE=\"古籍\" OR TYPE=\"外文图书\" OR synUpdateType:2)";
                    searchname += " 且 (资源类型=\"" + $($("#p_zy").find("input[type='checkbox']:checked")[i]).attr("title") + "\")";
                } else {
                    search += " (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\" OR TYPE=\"古籍\" OR TYPE=\"外文图书\" OR synUpdateType:2)";
                    searchname += " (资源类型=\"" + $($("#p_zy").find("input[type='checkbox']:checked")[i]).attr("title") + "\")";
                }
                break
            } else {
                if ((i + 1) == $("#p_zy").find("input[type='checkbox']:checked").length) {
                    if (temp == "期刊") {
                        type += " (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\")";
                    } else if (temp == "中文期刊") {
                        type += "  (TYPE=\"中文期刊文章\" AND -synUpdateType:2)  ";
                    } else if (temp == "外文期刊") {
                        type += " TYPE=\"外文期刊文章\"  ";
                    } else if (temp == "优先发布论文") {
                        type += " synUpdateType:2 ";
                    } else if (temp == "集刊") {
                        type += " TYPE=\"集刊文章\" ";
                    } else {
                        type += " TYPE=\"" + temp + "\"";
                    }
                    type_2 += "资源类型=\"" + $($("#p_zy").find("input[type='checkbox']:checked")[i]).attr("title") + "\"";
                } else {
                    if (temp == "期刊") {
                        type += " (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\")  OR ";
                    } else if (temp == "中文期刊") {
                        type += "  (TYPE=\"中文期刊文章\" AND -synUpdateType:2)  OR ";
                    } else if (temp == "外文期刊") {
                        type += " TYPE=\"外文期刊文章\"  OR ";
                    } else if (temp == "优先发布论文") {
                        type += " synUpdateType:2  OR ";
                    } else if (temp == "集刊") {
                        type += " TYPE=\"集刊文章\" OR ";
                    } else {
                        type += " TYPE=\"" + temp + "\" OR ";
                    }
                    type_2 += "资源类型=\"" + $($("#p_zy").find("input[type='checkbox']:checked")[i]).attr("title") + "\" 或 ";
                }
            }
        }
        if (type.length > 0) {
            if (search.length > 0) {
                search += " AND (" + type + ") ";
                if (searchname.length > 0) {
                    searchname += " 且 (" + type_2 + ")";
                } else {
                    searchname += "(" + type_2 + ")";
                }

            } else {
                search += type;
                searchname += type_2;
            }
        }
    }
    // 优先发布选择项
    if ($("#p_zy2").find("input[type='checkbox']:checked").length > 0 && $("#p_zy2").css("display") == "block") {
        type_2 = "";
        for (var i = 0; i < $("#p_zy2").find("input[type='checkbox']:checked").length; i++) {
            var temp = $($("#p_zy2").find("input[type='checkbox']:checked")[i]).val();
            if (temp == "优先发布论文") {
                if (search.length > 0) {
                    search += " AND (synUpdateType:2)";
                    searchname += " 且 (资源类型=\"" + $($("#p_zy2").find("input[type='checkbox']:checked")[i]).attr("title") + "\")";
                } else {
                    search += " (synUpdateType:2)";
                    searchname += " (资源类型=\"" + $($("#p_zy2").find("input[type='checkbox']:checked")[i]).attr("title") + "\")";
                }
                break
            }
        }
        if (type.length > 0) {
            if (search.length > 0) {
                search += " AND (" + type + ") ";
                if (searchname.length > 0) {
                    searchname += " 且 (" + type_2 + ")";
                } else {
                    searchname += "(" + type_2 + ")";
                }

            } else {
                search += type;
                searchname += type_2;
            }
        }
    }
    if ($("#p_qk").find("input[type='checkbox']:checked").length > 0) {
        type_2 = "";
        for (var i = 0; i < $("#p_qk").find("input[type='checkbox']:checked").length; i++) {
            var temp = $($("#p_qk").find("input[type='checkbox']:checked")[i]).val();
            if (temp == "全部期刊") {
                if (search.length > 0) {
                    search += " AND (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\")";
                    searchname += " 且 (期刊类型=\"" + $($("#p_qk").find("input[type='checkbox']:checked")[i]).attr("title") + "\")";
                } else {
                    search += " (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\")";
                    searchname += " (期刊类型=\"" + $($("#p_qk").find("input[type='checkbox']:checked")[i]).attr("title") + "\")";
                }
                break;
            } else {
                if ((i + 1) == $("#p_qk").find("input[type='checkbox']:checked").length) {
                    RA += " RANE=" + temp + "";
                    type_2 += "期刊类型=\"" + $($("#p_qk").find("input[type='checkbox']:checked")[i]).attr("title") + "\"";
                } else {
                    RA += " RANE=" + temp + " OR ";
                    type_2 += "期刊类型=\"" + $($("#p_qk").find("input[type='checkbox']:checked")[i]).attr("title") + "\" 或 ";
                }
            }

        }
        if (RA.length > 0) {
            if (search.length > 0) {
                search += " AND (" + RA + ") ";
                searchname += " 且 (" + type_2 + ")";
            } else {
                search += RA;
                searchname += type_2;
            }
        }
    }
    if ($("#p_qk").find("input[type='radio']:checked").length > 0) {
        type_2 = "";
        for (var i = 0; i < $("#p_qk").find("input[type='radio']:checked").length; i++) {
            var temp = $($("#p_qk").find("input[type='radio']:checked")[i]).val();
            if (temp == "全部期刊") {
                if (type_navyx == 6) {
                    if (search.length > 0) {
                        search += " AND (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\")";
                        searchname += " 且 (期刊类型=\"" + $($("#p_qk").find("input[type='radio']:checked")[i]).attr("title") + "\")";
                    } else {
                        search += " (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\")";
                        searchname += " (期刊类型=\"" + $($("#p_qk").find("input[type='radio']:checked")[i]).attr("title") + "\")";
                    }
                    break;
                } else {
                    if (search.length > 0) {
                        search += " AND (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\")";
                        searchname += " 且 (期刊类型=\"" + $($("#p_qk").find("input[type='radio']:checked")[i]).attr("title") + "\")";
                    } else {
                        search += " (TYPE=\"外文期刊文章\" OR TYPE=\"中文期刊文章\" OR TYPE=\"集刊文章\")";
                        searchname += " (期刊类型=\"" + $($("#p_qk").find("input[type='radio']:checked")[i]).attr("title") + "\")";
                    }
                    break;
                }
            } else {
                if ((i + 1) == $("#p_qk").find("input[type='radio']:checked").length) {
                    RA += " RANE=" + temp + "";
                    type_2 += "期刊类型=\"" + $($("#p_qk").find("input[type='radio']:checked")[i]).attr("title") + "\"";
                } else {
                    RA += " RANE=" + temp + " OR ";
                    type_2 += "期刊类型=\"" + $($("#p_qk").find("input[type='radio']:checked")[i]).attr("title") + "\" 或 ";
                }
            }

        }
        if (RA.length > 0) {
            if (search.length > 0) {
                search += " AND (" + RA + ") ";
                searchname += " 且 (" + type_2 + ")";
            } else {
                search += RA;
                searchname += type_2;
            }
        }
    }
    if ($("#p_xkfl").find("input[type='checkbox']:checked").length > 0) {
        type_2 = "";
        CLAS = "CLAS=*"
        for (var i = 0; i < $("#p_xkfl").find("input[type='checkbox']:checked").length; i++) {
            var temp = $($("#p_xkfl").find("input[type='checkbox']:checked")[i]).val();
            if ((i + 1) == $("#p_xkfl").find("input[type='checkbox']:checked").length) {
                CLAS += temp + "*";
                type_2 += "学科分类=\"" + $($("#p_xkfl").find("input[type='checkbox']:checked")[i]).attr("title") + "\"";
            } else {
                CLAS += temp + ",";
                type_2 += "学科分类=\"" + $($("#p_xkfl").find("input[type='checkbox']:checked")[i]).attr("title") + "\" 或 ";
            }
        }
        if (CLAS.length > 0) {
            if (search.length > 0) {
                search += " AND (" + CLAS + ") ";
                searchname += " 且 (" + type_2 + ")";
            } else {
                search += CLAS;
                searchname += type_2;
            }
        }
    }
    if ($("#p_y").find("input[type='checkbox']:checked").length > 0) {
        type_2 = "";
        for (var i = 0; i < $("#p_y").find("input[type='checkbox']:checked").length; i++) {
            var temp = $($("#p_y").find("input[type='checkbox']:checked")[i]).val();
            if ((i + 1) == $("#p_y").find("input[type='checkbox']:checked").length) {
                language += " LNGE=\"" + temp + "\"";
                type_2 += "语言=\"" + $($("#p_y").find("input[type='checkbox']:checked")[i]).attr("title") + "\"";
            } else {
                language += " LNGE=\"" + temp + "\" OR ";
                type_2 += "语言=\"" + $($("#p_y").find("input[type='checkbox']:checked")[i]).attr("title") + "\" 或 ";
            }
        }
        if (language.length > 0) {
            if (search.length > 0) {
                search += " AND (" + language + ") ";
                searchname += " 且 (" + type_2 + ")";
            } else {
                search += language;
                searchname += type_2;
            }
        }
    }
    if (search.length > 0) {
        if (AntiSqlValid(search) == true) {
            search = $.base64.encode(search, 'utf8');
            searchname = $.base64.encode(searchname, 'utf8');
            var urlAll = "/Literature/articlelist?sType=1&search=" + search + "&searchname=" + searchname + "&nav=0";
            var urlPrp = "/Literature/prplist?sType=1&search=" + search + "&searchname=" + searchname + "&nav=" + type_navyx + "&synUpdateType=2";
            if (ajaxKeys) {
                ajaxKeys = $.base64.encode(ajaxKeys, 'utf8');
                urlAll += "&ajaxKeys=" + ajaxKeys;
                urlPrp += "&ajaxKeys=" + ajaxKeys;
            }
            if (type_navyx == "6") {
                window.open(filterXSS(urlPrp));
            } else {
                window.open(filterXSS(urlAll));
            }
        }
    } else {
        layer.msg("检索条件不能为空！");
    }
}

// 外文图书高级检索
function waiwen_search() {
    var search = ""; //拼接完后的查询表达式
    var searchww = {
        firstHigh: "",
        secondHigh: "",
        thirdHigh: "",
        fourthHigh: "",
        fifthHigh: "",
        firstCondition: "",
        secondCondition: "",
        thirdCondition: "",
        fourthCondition: "",
        firstAccurate: "",
        secondAccurate: "",
        thirdAccurate: "",
        fourthAccurate: "",
        fifthAccurate: "",
        languageHigh: "",
        startTimeHigh: "",
        endTimeHigh: "",
        sType:1,
        synUpdateType:4,
        keyword:"",
    }
    var ajaxKeys = ""; //检索词回显
    if ($("#u_txt_1ww").val().length > 0) {
        var text = $("#u_txt_1ww").val();
        search += "firstHigh=" + $("#u_select2_1_ww").val() + "=" + text + "&firstAccurate=" + $("#u_select1_1ww").val()
        searchww.firstHigh = $("#u_select2_1_ww").val() + "=" + text
        searchww.firstAccurate = $("#u_select1_1ww").val()
        ajaxKeys += chuancanhuixian($("#u_select2_1_ww").val()) + text
        searchww.keyword += $("#u_select2_1_ww").val() + "=" + text
    }
    if ($("#u_txt_2ww").val().length > 0) {
        var text = $("#u_txt_2ww").val();
        if (search.length > 0) {
            search += "&firstCondition=" + $("#u_select3_2ww").val() + "&secondHigh=" + $("#u_select2_2_ww").val() + "=" + text + "&secondAccurate=" + $("#u_select1_2ww").val()

            searchww.firstCondition = $("#u_select3_2ww").val()
            searchww.secondHigh = $("#u_select2_2_ww").val() + "=" + text
            searchww.secondAccurate = $("#u_select1_2ww").val()

            ajaxKeys += ',' + chuancanhuixian($("#u_select2_2_ww").val()) + text;
            searchww.keyword += ',' + $("#u_select2_2_ww").val() + "=" + text
        } else {
            search += "secondHigh=" + $("#u_select2_2_ww").val() + "=" + text + "&secondAccurate=" + $("#u_select1_2ww").val()

            searchww.secondHigh = $("#u_select2_2_ww").val() + "=" + text
            searchww.secondAccurate = $("#u_select1_2ww").val()

            ajaxKeys += chuancanhuixian($("#u_select2_2_ww").val()) + text;
            searchww.keyword += $("#u_select2_2_ww").val() + "=" + text
        }
    }
    if ($("#u_txt_3ww").val().length > 0) {
        var text = $("#u_txt_3ww").val();
        if (search.length > 0) {
            search += "&secondCondition=" + $("#u_select3_3ww").val() + "&thirdHigh=" + $("#u_select2_3_ww").val() + "=" + text + "&thirdAccurate=" + $("#u_select1_3ww").val()

            searchww.secondCondition = $("#u_select3_3ww").val()
            searchww.thirdHigh = $("#u_select2_3_ww").val() + "=" + text
            searchww.thirdAccurate = $("#u_select1_3ww").val()

            ajaxKeys += ',' + chuancanhuixian($("#u_select2_3_ww").val()) + text;
            searchww.keyword += ',' + $("#u_select2_3_ww").val() + "=" + text;
        } else {
            search += "thirdHigh=" + $("#u_select2_3_ww").val() + "=" + text + "&thirdAccurate=" + $("#u_select1_3ww").val()

            searchww.thirdHigh = $("#u_select2_3_ww").val() + "=" + text
            searchww.thirdAccurate = $("#u_select1_3ww").val()

            ajaxKeys += chuancanhuixian($("#u_select2_3_ww").val()) + text;
            searchww.keyword += $("#u_select2_3_ww").val() + "=" + text;
        }
    }
    if ($("#u_txt_4ww").val().length > 0) {
        var text = $("#u_txt_4ww").val();
        if (search.length > 0) {
            search += "&thirdCondition=" + $("#u_select3_4ww").val() + "&fourthHigh=" + $("#u_select2_4_ww").val() + "=" + text + "&fourthAccurate=" + $("#u_select1_4ww").val()

            searchww.thirdCondition = $("#u_select3_4ww").val()
            searchww.fourthHigh = $("#u_select2_4_ww").val() + "=" + text
            searchww.fourthAccurate = $("#u_select1_4ww").val()

            ajaxKeys += ',' + chuancanhuixian($("#u_select2_4_ww").val()) + text;
            searchww.keyword += ',' + $("#u_select2_4_ww").val() + "=" + text;
        } else {
            search += "thirdHigh=" + $("#u_select2_4_ww").val() + "=" + text + "&fourthAccurate=" + $("#u_select1_4ww").val()

            searchww.fourthHigh = $("#u_select2_4_ww").val() + "=" + text
            searchww.fourthAccurate = $("#u_select1_4ww").val()

            ajaxKeys += chuancanhuixian($("#u_select2_4_ww").val()) + text;
            searchww.keyword += $("#u_select2_4_ww").val() + "=" + text;
        }
    }
    if ($("#u_txt_5ww").val().length > 0) {
        var text = $("#u_txt_5ww").val();
        if (search.length > 0) {
            search += "&fourthCondition=" + $("#u_select3_5ww").val() + "&fifthHigh=" + $("#u_select2_5_ww").val() + "=" + text + "&fifthAccurate=" + $("#u_select1_5ww").val()

            searchww.fourthCondition = $("#u_select3_5ww").val()
            searchww.fifthHigh = $("#u_select2_5_ww").val() + "=" + text
            searchww.fifthAccurate = $("#u_select1_5ww").val()

            ajaxKeys += ',' + chuancanhuixian($("#u_select2_5_ww").val()) + text;
            searchww.keyword += ',' + $("#u_select2_5_ww").val() + "=" +text;
        } else {
            search += "fifthHigh=" + $("#u_select2_5_ww").val() + "=" + text + "&fifthAccurate=" + $("#u_select1_5ww").val()

            searchww.fifthHigh = $("#u_select2_5_ww").val() + "=" + text
            searchww.fifthAccurate = $("#u_select1_5ww").val()

            ajaxKeys += chuancanhuixian($("#u_select2_5_ww").val()) + text;
            searchww.keyword += $("#u_select2_5_ww").val() + "=" +text;
        }
    }
    if ($("#date_startww").val().length > 0) {
        var time1 = new Date($("#date_startww").val());
        if ($("#date_endww").val().length > 0) {
            var time2 = new Date($("#date_endww").val());
            if (search.length > 0) {
                search += "&startTimeHigh=" + time1.format("yyyy") + " &endTimeHigh" + time2.format("yyyy") + "]";
                ajaxKeys += " 且 时间=" + time1.format("yyyy-MM-dd") + " 至 " + time2.format("yyyy-MM-dd");
            } else {
                search += "startTimeHigh=" + time1.format("yyyy") + " &endTimeHigh" + time2.format("yyyy") + "]";
                // search += " years:[" + time1.format("yyyy") + " TO " + time2.format("yyyy") + "]";
                ajaxKeys += " 时间=" + time1.format("yyyy-MM-dd") + " 至 " + time2.format("yyyy-MM-dd");
            }
            searchww.startTimeHigh = time1.format("yyyy")
            searchww.endTimeHigh = time2.format("yyyy")
        } else {
            const now = new Date();
            const year = now.getFullYear();
            searchww.startTimeHigh = time1.format("yyyy")
            // searchww.fifthAccurate = year
            if (search.length > 0) {
                search += "&startTimeHigh=" + time1.format("yyyy") + " &endTimeHigh" + year + "]";
                // search += " AND years:[" + time1.format("yyyy") + " TO * ]";
                ajaxKeys += " 且 时间=" + time1.format("yyyy-MM-dd") + " 至今";
            } else {
                // search += " years:[" + time1.format("yyyy") + " TO * ]";
                search += "startTimeHigh=" + time1.format("yyyy") + " &endTimeHigh" + year + "]";
                ajaxKeys += "时间=" + time1.format("yyyy-MM-dd") + " 至今";
            }
        }
    }else{
        if ($("#date_endww").val().length > 0) {
            layer.msg("请选择起始时间！");
            return;
        }
    }
    if ($("#p_yww").find("input[type='radio']:checked").length > 0) {
        type_2 = "";
        for (var i = 0; i < $("#p_yww").find("input[type='radio']:checked").length; i++) {
            var temp = $($("#p_yww").find("input[type='radio']:checked")[i]).val();
            if ((i + 1) == $("#p_yww").find("input[type='radio']:checked").length) {
                type_2 += "语种=\"" + $($("#p_yww").find("input[type='radio']:checked")[i]).attr("title") + "\"";
            } else {
                type_2 += "语种=\"" + $($("#p_yww").find("input[type='radio']:checked")[i]).attr("title") + "\" 或 ";
            }
            // searchww.languageHigh = $($("#p_yww").find("input[type='radio']:checked")[i]).attr("title")
            searchww.languageHigh = $($("#p_yww").find("input[type='radio']:checked")[i]).attr("value")
        }
        if (search.length > 0) {
            search += "&languageHigh=" + $($("#p_yww").find("input[type='radio']:checked")[i]).attr("value")
            ajaxKeys += " 且 (" + type_2 + ")";
        } else {
            search += "languageHigh=" + $($("#p_yww").find("input[type='radio']:checked")[i]).attr("value")
            ajaxKeys += type_2;
        }
    }
    if (search.length > 0) {
        if (AntiSqlValid(search) == true) {
            // search = $.base64.encode(search, 'utf8');
            searchcc = $.base64.encode(JSON.stringify(searchww), 'utf8')
            // var urlAll = "/ForeignBooks/getForeignBookQueryUrl?search=" + search;
            var urlAll = "/ForeignBooks/getForeignBookQueryUrl?searchH=" + searchcc;
            if (ajaxKeys) {
                ajaxKeys = $.base64.encode(ajaxKeys, 'utf8');
                urlAll += "&searchname=" + ajaxKeys;
            }
            window.open(filterXSS(urlAll));
        }
    } else {
        layer.msg("检索条件不能为空！");
    }
}

// 传参回显数据
function chuancanhuixian(val) {
    var texte = ''
    if (val == "name") {
        texte = "书名="
    } else if (val == "zuoZhe") {
        texte = "作者="
    } else if (val == "BanZhe") {
        texte = "编者="
    } else if (val == "IS") {
        texte = "eISBN="
    } else if (val == "BanCi") {
        texte = "版次="
    } else if (val == "ChuBanShe") {
        texte = "出版社="
    } else if (val == "JanJie") {
        texte = "内容简介="
    }
    return texte;
}

//拼装下拉框条件
function selectwhere(select2, text, select1) {
    var search = "";
    if (select2 == "TS") {
        if (select1 == "1") //模糊查询
        {
            search = "(IKTE=" + text + " OR IKPYTE=" + text + " OR IKST=" + text + " OR IKET=" + text + " OR IKSE=" + text + ")";
        } else { //精确查询
            search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\" OR IKST=\"" + text + "\" OR IKET=\"" + text + "\" OR IKSE=\"" + text + "\")";
        }
        Advancedname = "题名/关键词=\"" + text + "\"";
    } else if (select2 == "TITE") {
        if (select1 == "1") //模糊查询
        {
            search = "(IKTE=" + text + " OR IKPYTE=" + text + " OR IKET=" + text + ")";
        } else { //精确查询
            search = "(IKTE=\"" + text + "\" OR IKPYTE=\"" + text + "\" OR IKET=\"" + text + "\")";
        }
        Advancedname = "题名=\"" + text + "\"";
    } else if (select2 == "CRTR") {
        if (select1 == "1") //模糊查询
        {
            search = "(IKCR=" + text + " OR IKCE=" + text + " OR IKCRE=" + text + ")";
        } else {//精确查询
            search = "((CRTR=*" + text + "* OR IKCE=\"" + text + "\")" + " AND (ik_creator:\"" + text + "\"^20) OR (IKCRE=\"" + text + "\"))";
        }
        Advancedname = "作者=\"" + text + "\"";
    } else if (select2 == "IKST") {
        if (select1 == "1") //模糊查询
        {
            search = "(IKST=" + text + " OR IKSE=" + text + ")";
        } else { //精确查询
            search = "(SJET=*" + text + "* OR IKSE=\"" + text + "\")";
        }
        Advancedname = "关键词=\"" + text + "\"";
    } else if (select2 == "ISSN") {
        if (select1 == "1") //模糊查询
        {
            search = "ISSN=*" + text + "*";
        } else { //精确查询
            search = "ISSN=" + text;
        }
        Advancedname = "ISSN=\"" + text + "\"";
    } else if (select2 == "CNEM") {
        if (select1 == "1") //模糊查询
        {
            search = "(CNEM=*" + text + "*" + " OR CNEME=" + text + ")";
        } else { //精确查询
            search = "(CNEM=\"" + text + "\" OR CNEME=\"" + text + "\")";
        }
        Advancedname = "出版物名称=\"" + text + "\"";
    } else if (select2 == "IKTS") {
        if (select1 == "1") //模糊查询
        {
            search = "IKTS=" + text;
        } else { //精确查询
            search = "IKTS=\"" + text + "\"";
        }
        Advancedname = "出版社=\"" + text + "\"";
    } else if (select2 == "IKIS") {
        if (select1 == "1") //模糊查询
        {
            search = "(IKIS=" + text + " OR IKISE=" + text + ")";
        } else { //精确查询
            search = "(IKIS=\"" + text + "\" OR IKISE=\"" + text + "\")";
        }
        Advancedname = "机构=\"" + text + "\"";
    } else if (select2 == "CLAS") {
        if (select1 == "1") //模糊查询
        {
            search = "CLAS=*" + text + "*";
        } else { //精确查询
            search = "CLAS=" + text;
        }
        Advancedname = "中图分类号=\"" + text + "\"";
    } else if (select2 == "IKRK") {
        if (select1 == "1") //模糊查询
        {
            search = "(IKRK=" + text + " OR IKRKE=" + text + ")";
        } else { //精确查询
            search = "(IKRK=\"" + text + "\" OR IKRKE=\"" + text + "\")";
        }
        Advancedname = "摘要=\"" + text + "\"";
    } else if (select2 == "IMBE") {
        if (select1 == "1") //模糊查询
        {
            search = "IMBE=*" + text + "*";
        } else { //精确查询
            search = "IMBE=" + text;
        }
        Advancedname = "基金资助=\"" + text + "\"";
    }
    return search;
}

//期刊高级检索
function qkSearchCondition() {
    var pa = "";
    var core = "";
    var searchType = "";
    $("#qkadvancetab").find('input[type=text]').each(function () {
        if ($(this).val().length > 0) {
            pa += "_" + $(this).attr("name") + ":" + $(this).val();
        }
    });
    searchType = $("#searchType").val();
    $("input[name='Vip_Ext0_MRange']:radio:checked").each(function () {
        core += $(this).val();
    });
    pa = "h=core:" + core + pa + "_searchType:" + searchType;
    window.open(filterXSS("/journal/list?e=" + encodeURIComponent(pa) + "&langType=" + $("input[name='radLangType']:checked").val()));
}

//高级检索选项卡功能
function Show_ASearch(obj) {
    var temp = $(obj).attr("id");
    $(obj).addClass("current");
    $(obj).nextAll().removeClass("current");
    $(obj).prevAll().removeClass("current");
    if (temp == "article") {
        $("#search_article").show();
        $("#Search_text").hide();
        $("#cnt2").hide();
        $("#div_TS").hide();
        $("#div_GJ").hide();
        $("#search_waiwen").hide();

    }
    if (temp == "QK") {
        $("#search_article").hide();
        $("#Search_text").hide();
        $("#cnt2").show();
        $("#div_TS").hide();
        $("#div_GJ").hide();
        $("#search_waiwen").hide();
    }
    if (temp == "book") {
        $("#search_article").hide();
        $("#Search_text").hide();
        $("#cnt2").hide();
        $("#div_TS").show();
        $("#div_GJ").hide();
        $("#search_waiwen").hide();
    }
    if (temp == "gj") {
        $("#search_article").hide();
        $("#Search_text").hide();
        $("#cnt2").hide();
        $("#div_TS").hide();
        $("#div_GJ").show();
        $("#search_waiwen").hide();
    }
    if (temp == "expression") {
        $("#search_article").hide();
        $("#cnt2").hide();
        $("#div_TS").hide();
        $("#Search_text").show();
        $("#div_GJ").hide();
        $("#search_waiwen").hide();
    }
    if (temp == "waiwen") {
        $("#search_article").hide();
        $("#cnt2").hide();
        $("#div_TS").hide();
        $("#Search_text").hide();
        $("#div_GJ").hide();
        $("#search_waiwen").show();
        if(languageDataLoaded){GetLanguage()};
    }
}

//检索表达式检索
function Search_text() {
    var search = "";
    var searchCH = "";
    var type = "";
    var type_2 = "";
    search = $("#txt_seach").val();

    if (search.length > 0) {
        searchCH = Get_searchname(search);
        if ($("#p_atype").find("input[type='checkbox']:checked").length > 0) {
            for (var i = 0; i < $("#p_atype").find("input[type='checkbox']:checked").length; i++) {
                var temp = $($("#p_atype").find("input[type='checkbox']:checked")[i]).val();
                if (temp == "全部") {
                    search += " TYPE=*";
                    searchCH += "资源类型=\"全部\"";
                    break;
                } else {
                    if ((i + 1) == $("#p_atype").find("input[type='checkbox']:checked").length) {
                        type += " TYPE=*" + temp + "*";
                        type_2 += "资源类型=\"" + $($("#p_atype").find("input[type='checkbox']:checked")[i]).attr("title") + "\"";
                    } else {
                        type += " TYPE=*" + temp + "* OR ";
                        type_2 += "资源类型==\"" + $($("#p_atype").find("input[type='checkbox']:checked")[i]).attr("title") + "\" 或 ";
                    }
                }

            }
        }
        if (type.length > 0) {
            search += " AND (" + type + ") ";
            searchCH += " 且 (" + type_2 + ")";
        }
        if (search.length > 0) {
            if (AntiSqlValid(search) == true) {
                var searchCS = sumaut(search, "IKCR=")
                for (var i = 0; i < searchCS; i++) {
                    search = authorTH(search)
                }
                search = $.base64.encode(search, 'utf8');
                searchCH = $.base64.encode(searchCH, 'utf8');
                window.open(filterXSS("/Literature/articlelist?search=" + search + "&searchname=" + searchCH + "&nav=0"));
            }
        }
    } else {
        layer.msg("表达式不能为空！");
    }
}

// 处理检索表达式作者
function authorTH(jppp) {
    var search = jppp, newStr
    if (search.indexOf("IKCR=\"") > -1 && search.slice(search.indexOf("IKCR=") + 5, search.indexOf("IKCR=") + 6) == "\"") {
        var ff = search.indexOf("IKCR=\"")  //返回的是作者字段的起始位置
        var gg = search.indexOf("\"", ff + 6)  //返回的是作者字段的结束位置
        var jj = search.substring(ff + 6, gg)  // 返回的是作者名字字段
        newStr = search.slice(0, ff) + "creators:" + jj + search.slice(gg + 1);
    } else if (search.indexOf("IKCR=") > -1 && search.slice(search.indexOf("IKCR=") + 5, search.indexOf("IKCR=") + 6) != "\"") {
        var f = search.indexOf("IKCR=")  // 获取作者字段的起始位置
        var g = search.slice(f + 5)   // 获取从作者开始到结束字符
        var h, j //声明从名字到结束的下标
        if (g.indexOf(" AND ") > -1) {
            h = g.indexOf(" AND ")
        } else if (g.indexOf(" OR ") > -1) {
            h = g.indexOf(" OR ")
        } else if (g.indexOf(" NOT ") > -1) {
            h = g.indexOf(" NOT ")
        }
        if (h != undefined) {
            j = g.slice(0, h)
            newStr = search.slice(0, f) + "creators:*" + j + "*" + g.slice(h);
        } else {
            j = g.slice(0)
            newStr = search.slice(0, f) + "creators:*" + j + "*";
        }
    }
    return "(" + newStr + " AND ik_creator:\"" + j + "\"^20)"
}

// 统计字符出现次数
function sumaut(str, a) {
    let b = str.indexOf(a);
    var num = 0;
    while (b !== -1) {
        num++;
        b = str.indexOf(a, b + 1)
    }
    return num;
}

//古籍高级检索
function Search_GJ() {
    var title = $("#gj_title").val();
    var classname = $("#gj_classname").val();
    var num = $("#gj_num").val();
    var barcodenum = $("#gj_barcodenum").val();
    var creator = $("#gj_author_c").val();
    var tspress = $("#gj_press").val();
    var date = $("#gj_pubdate").val();
    var isbn = $("#gj_isbn").val();
    var search = " TYPE=古籍";
    var searchCH = "类型=\"古籍\"";
    if (title.length > 0) {
        //search += " AND IKTENUMM=\"" + title + "\"";
        search += " AND IKTE=\"" + title + "\"";
        searchCH += " 与 题名=\"" + title + "\"";
    }
    if (classname.length > 0) {
        search += " AND CLNE=\"" + classname + "\"";
        searchCH += "与 分类=\"" + classname + "\"";
    }
    if (num.length > 0) {
        search += " AND NUMM=*" + num + "*";
        searchCH += "与 册数=\"" + num + "\"";
    }
    if (barcodenum.length > 0) {
        search += " AND BDNM=\"" + barcodenum + "\"";
        searchCH += "与 条码号=\"" + barcodenum + "\"";
    }
    if (creator.length > 0) {
        search += " AND IKCR=\"" + creator + "\"";
        searchCH += "与 责任者=\"" + creator + "\"";
    }
    if (tspress.length > 0) {
        search += " AND IKTS=\"" + tspress + "\"";
        searchCH += "与 出版者=\"" + tspress + "\"";
    }
    if (date.length > 0) {
        search += " AND PBDE=\"" + date + "\"";
        searchCH += "与 出版时间=\"" + date + "\"";
    }
    if (isbn.length > 0) {
        search += " AND ISBN=*" + isbn + "*";
        searchCH += "与 索书号=\"" + isbn + "\"";
    }
    if (changValue2(title).length > 0 || changValue2(classname).length > 0 || changValue2(num).length > 0 || changValue2(barcodenum).length > 0 || changValue2(creator).length > 0 || changValue2(tspress).length > 0 || changValue2(date).length > 0 || changValue2(isbn).length > 0) {
        if (AntiSqlValid(search) == true) {
            search = $.base64.encode(search, 'utf8');
            searchCH = $.base64.encode(searchCH, 'utf8');
            window.open(filterXSS("/Literature/ancientbooklistNew?search=" + search + "&searchname=" + searchCH + "&nav=5"));
        }

    } else {
        layer.msg("检索条件不能为空！");
    }
}

//文献搜索转译特殊字符
function addEscape(value) {
    // let arr = ['(', '[', '{', '/', '^', '$', '¦', '}', ']', ')', '?', '*', '+', '.', "'", '"']
    let arr = [':', "'", '"', '\\']
    for (let i = 0; i < arr.length; i++) {
        if (value) {
            if (value.indexOf(arr[i]) > -1) {
                // const reg = (str) => str.replace(/[\[\]\/\{\}\(\)\*\'\"\¦\+\?\.\\\^\$\|]/g, "\\$&")
                const reg = (str) => str.replace(/[\'\"\:\\]/g, "\\$&")
                value = reg(value)
            }
        }

    }
    return value;
}

function Get_searchname(search) {
    var searchN = "";
    searchN = search.replace("IKTE=", "题名=").replace("IKET=", "英文标题=").replace("IKCR=", "作者=").replace("IKCE=", "英文作者=").replace("IKST=", "关键词=").replace("IKSE=", "英文关键词=").replace("DATE=", "日期=").replace("TYPE=", "文献类型=").replace("LNGE=", "语言=").replace("CLAS=", "中图分类=").replace("CNEM=", "出版物名称=").replace("IKTS=", "出版社=").replace("IKIS=", "机构=").replace("ISSN=", "issn=").replace("IMBE=", "基金资助=").replace("QKCS=", "期刊类型=").replace("BNEM=", "图书名称=").replace("SENE=", "丛书名=").replace("ISBN=", "isbn（索书号）=").replace("DITY=", "目录=").replace("BOKO=", "书号=").replace("CLNE=", "分类=").replace("NUMM=", "册数=").replace("BDNM=", "条码号=").replace("PBDE=", "出版时间=").replace("RANE=", "期刊类型=").replace("PDNE=", "出版时间=").replace("SETN=", "版本=").replace("CLNE=", "分类=").replace("BDNM=", "条码号=").replace("PKNM=", "包号=").replace("IKRK=", "摘要=").replace("IKPYTE=", "拼音=");
    return searchN;
}

function openadvaqkclass() {
    $("#advanceqkclass").show();
}

function closeadvaqkclass() {
    $("#advanceqkclass").hide();
}

function seleadvqkclass() {
    var classstr = "";
    $("#listclassdiv input[type=checkbox]:checked").each(function () {
        classstr += "," + $(this).val();
    });
    if (classstr.length > 0) {
        classstr = classstr.substring(1);
    }
    classstr = classstr.replace(/\+/g, ",");
    $("#qkselclass").val(classstr);
    $("#advanceqkclass").hide();
}

//外文图书分类号
function openadvatsclass() {
    $("#advancetsclass").show();
}

function closeadvatsclass() {
    $("#advancetsclass").hide();
}

function seleadvtsclass() {
    var classstr = "";
    $("#listtsclassdiv input[type=checkbox]:checked").each(function () {
        classstr += "," + $(this).val();
    });
    if (classstr.length > 0) {
        classstr = classstr.substring(1);
    }
    classstr = classstr.replace(/\+/g, ",");
    $("#ts_class").val(classstr);
    $("#advancetsclass").hide();
}

//判断是否登录
function checkLogin() {
    var temp = false;
    $.ajax({
        type: "GET",
        url: "/login/check?r=" + Math.random(),
        data: '',
        async: false,
        dataType: 'json',
        success: function (data) {
            if (data.succee && data.user) {
                temp = true;
                userInfo = data.user;
            } else {
                temp = false;
            }
        }
    });
    return temp;
}

//处理null,undefined,空值
function changValue(value) {
    if (typeof (value) == "undefined" || value == "" || value == "null" || value == null) {
        value = "暂无";
    }
    return value;
}

//处理null,undefined,空值
function changValue2(value) {
    if (typeof (value) == "undefined" || value == "" || value == "null" || value == null) {
        value = "";
    }
    return value;
}

//防止SQL注入
function AntiSqlValid(text) {
    re = /select |update |insert |delete |exec |count |;|>|<|%/i;
    var temp = true;
    if (re.test(text)) {
        temp = false;
        layer.msg("请您不要在参数中输入特殊字符和SQL关键字！"); //注意中文乱码
    }
    return temp;
}

// 限制input输入最大长度
function setupDynamicMaxlength(element, chineseLimit = 200, englishLimit = 300) {
    const input = typeof element === 'string' ? document.querySelector(element) : element;
    if (!input) return;
    const checkAndSetLimit = () => {
        const hasChinese = /[\u4e00-\u9fa5]/.test(input.value);
        input.maxLength = hasChinese ? chineseLimit : englishLimit;
    };
    input.addEventListener('input', checkAndSetLimit);
    checkAndSetLimit();
}

//高级检索清除功能
function clearcontent() {
    $("#search_article").find("input[type='text']").val("");
    $("#search_article").find("textarea").val("");
    $("#search_article").find("input[type=checkbox]:checked").click();
    $(".layui-form-checked").removeClass("layui-form-checked");
    $("#search_article").find("select").val("");
    $("#u_select2_1").val("TS")
    $("#u_select2_2").val("CRTR")
    $("#u_select2_3").val("CNEM")
    $("#u_select2_4").val("IKTS")
    $("#u_select2_5").val("IKIS")
    $("#u_select1_1").val("2")
    $("#u_select1_2").val("2")
    $("#u_select1_3").val("2")
    $("#u_select1_4").val("2")
    $("#u_select1_5").val("2")
    $("#p_qk").find("input[type=radio]").removeAttr("checked")
    initLayui();
}

function clearcontent2() {
    $("#search_waiwen").find("input[type='text']").val("");
    $("#search_waiwen").find("textarea").val("");
    $("#search_waiwen").find("input[type=checkbox]:checked").click();
    $(".layui-form-checked").removeClass("layui-form-checked");
    $("#search_waiwen").find("select").val("");
    $("#u_select2_1_ww").val("name")
    $("#u_select2_2_ww").val("zuoZhe")
    $("#u_select2_3_ww").val("BanZhe")
    $("#u_select2_4_ww").val("IS")
    $("#u_select2_5_ww").val("BanCi")
    $("#p_xkfl_ww").find("input[type=radio]").removeAttr("checked")
    $("#p_yuyan_ww").find("input[type=radio]").removeAttr("checked")
    initLayui();
}

//表单初始化！
function initLayui() {
    layui.use(['form', 'layer', 'layedit'], function () {
        var form = layui.form(),
            layer = layui.layer,
            layedit = layui.layedit;
        form.render(); //更新全部
    });
}

// 获取外文图书语种
function GetLanguage() {
    if (!document.getElementById('dynamic-radio-style')) {
        $('<style id="dynamic-radio-style">' +
            '.dynamic-radio-item { display: inline-block; margin-right: 15px; }' +
            '.dynamic-radio-mask { display: inline-block; cursor: pointer; user-select: none; }' +
            '.dynamic-radio-mask i { display: inline-block; width: 14px; height: 14px; border-radius: 50%; border: 1px solid #aaa; background: #fff; position: relative; top: 4px; margin-right: 5px; }' +
            '.dynamic-radio-mask.selected i { background: #d92b2a; border-color: #d92b2a; }' +
            '.dynamic-radio-mask.selected i:after { content: ""; display: block; width: 6px; height: 6px; background: #fff; border-radius: 50%; position: absolute; top: 4px; left: 4px; }' +
            '.dynamic-radio-mask span { vertical-align: middle; }' +
            '</style>').appendTo('head');
    }
    if (window.currentXHR) window.currentXHR.abort();
    window.currentXHR = $.ajax({
        type: "post",
        url: "/ForeignBooks/findSysType",
        data: { dictType: "外文图书_语言" },
        success: function(json) {
            var innerHtml = '';
            innerHtml += '<div class="dynamic-radio-item" data-value="">' +
                '<input type="radio" name="radLangTypeWW" value="" title="全部" style="display:none;" checked>' +
                '<div class="dynamic-radio-mask selected"><i></i><span>全部</span></div>' +
                '</div>';
            for (var i = 0; i < json.length; i++) {
                var code = json[i].code || '';
                var name = json[i].name || '';
                var safeName = name.replace(/[&<>]/g, function(m) {
                    if (m === '&') return '&amp;';
                    if (m === '<') return '&lt;';
                    if (m === '>') return '&gt;';
                    return m;
                });
                innerHtml += '<div class="dynamic-radio-item" data-value="' + code + '">' +
                    '<input type="radio" name="radLangTypeWW" value="' + code + '" title="' + safeName + '" style="display:none;">' +
                    '<div class="dynamic-radio-mask"><i></i><span>' + safeName + '</span></div>' +
                    '</div>';
            }
            $("#p_yww").html(innerHtml);
            $("#p_yww .dynamic-radio-mask").off('click').on('click', function() {
                var $mask = $(this);
                var $item = $mask.closest('.dynamic-radio-item');
                var $radio = $item.find('input[type="radio"]');
                if ($radio.prop('checked')) return;
                var name = $radio.attr('name');
                $('input[name="' + name + '"]').each(function() {
                    $(this).prop('checked', false);
                    $(this).closest('.dynamic-radio-item').find('.dynamic-radio-mask').removeClass('selected');
                });
                $radio.prop('checked', true);
                $mask.addClass('selected');
                $radio.trigger('change');
            });
            languageDataLoaded = false;
        },
        complete: function() { window.currentXHR = null; }
    });
}

// 设置期刊默认封面
function setJournalDefaultImg(img, classId) {
    if (classId == 7) { //中文期刊
        img.src = '/images/surfacePlot/cJournal.jpg';
        $(img).next()[0].style.display = 'block';
    } else if (classId == 10) { //外文期刊
        img.src = '/images/surfacePlot/eJournalX.jpg';
    } else {
        img.src = '/images/bookb5.png';
    }
}

//全文下载
function AddHandleCount(elmentobj, type, articleid, downcount, readcount, url, GCH, Class, Title, ShowWriter, periodname) {
    var click=$(elmentobj).attr("onclick"); //获取点击事件
    $(elmentobj).attr("onclick",""); //暂时取消点击事件,避免用户连续点击,当用户完成一次在线阅读或下载操作以后,在为该按钮附上点击事件
    GCH=changValue2(GCH);
    Class=changValue2(Class);
    ShowWriter=changValue2(ShowWriter);
    var obj={};
    obj.type=type;
    obj.articleid=articleid;
    obj.id=articleid;
    obj.periodname=periodname;
    obj.downcount=downcount;
    obj.readcount=readcount;
    obj.gch=GCH;
    obj.class=Class;
    obj.titleC=Title;
    obj.showWriter=ShowWriter;
    obj.pageType=pageType;
    if(type=="古籍") {
        obj.barcodeNum=url.split("=")[1];
    }
    $.ajax({
        type: "POST",
        url: "/Literature/readDownloadUrl",
        data: JSON.stringify(obj),
        contentType: "application/json; charset=utf-8",
        dataType: 'json',
        async: false,
        success: function(data) {
            if(data.code===500) {
                layer.msg(data.msg? data.msg:"抱歉，该文章暂无资源！");
                return false;
            }
            if(data.code===501) {
                layer.msg("抱歉，该文章暂无资源！");
                return false;
            }
            if (type == "古籍") {
                obj.barcodeNum = url.split("=")[1];
                layer.msg("检测到该资源较大，请耐心等待！", {
                    icon: 7,
                    time: 5000
                });
            }
            ms.util.getMinioSign(function (sign) {
                var xhr = new XMLHttpRequest();
                xhr.open('get', data.url, true);
                xhr.setRequestHeader("sign", sign);
                xhr.setRequestHeader("site", "npssd");
                xhr.setRequestHeader("dotype", "down");
                xhr.responseType = 'blob';
                xhr.onload = function () {
                    if (this.status == 200) {
                        var blob = this.response
                        var fileName = Title + '.pdf';
                        if ('download' in document.createElement('a')) {
                            //非IE下载
                            var elink = document.createElement('a');
                            elink.download = fileName;
                            elink.style.display = 'none';
                            elink.href = URL.createObjectURL(blob);
                            document.body.appendChild(elink);
                            elink.click();
                            URL.revokeObjectURL(elink.href);
                            document.body.removeChild(elink);
                        } else {
                            navigator.msSaveBlob(blob, fileName);
                        }
                    } else {
                        layer.msg("抱歉，该文章暂无资源！");
                    }
                }
                xhr.send()
            })
        }
    });
    $(elmentobj).attr("onclick", click); //执行完后再为按钮附上点击事件
}

//全文阅读
function ViewHandleCount(elmentobj, type, articleid, downcount, readcount, url, GCH, Class, Title, ShowWriter, periodname) {
    var click = $(elmentobj).attr("onclick"); //获取点击事件
    $(elmentobj).attr("onclick", ""); //暂时取消点击事件,避免用户连续点击,当用户完成一次在线阅读或下载操作以后,在为该按钮附上点击事件
    GCH = changValue2(GCH);
    Class = changValue2(Class);
    ShowWriter = changValue2(ShowWriter);
        var obj = {};
        obj.type = type;
        obj.articleid = articleid;
        obj.id = articleid;
        obj.periodname = periodname;
        obj.downcount = downcount;
        obj.readcount = readcount;
        obj.gch = GCH;
        obj.class = Class;
        obj.titleC = Title;
        obj.showWriter = ShowWriter;
        obj.pageType = pageType;
        if (type == "古籍") {
            obj.barcodeNum = url.split("=")[1];
        }
        $.ajax({
                type: "POST",
                url: "/Literature/readDownloadUrl",
                data: JSON.stringify(obj),
                contentType: "application/json; charset=utf-8",
                dataType: 'json',
                async: false,
                success: function (data) {
                    if (data.code === 500) {
                        layer.msg(data.msg ? data.msg : "抱歉，该文章暂无资源！");
                        return false;
                    }
                    if(data.code === 501){
                        layer.msg("抱歉，该文章暂无资源！");
                        return false;
                    }
                    if (type == "外文期刊文章") {
                        window.open(filterXSS(data.url));
                        return false;
                    }
                    if (type == "古籍") {
                        window.open(filterXSS('/Literature/fullTextRead?filePath=' + encodeURIComponent(data.url)));
                        return false;
                    }
                    ms.util.getMinioSign(function (sign) {
                        var xhr = new XMLHttpRequest();
                        xhr.open('get', data.url, true);
                        xhr.setRequestHeader("sign", sign);
                        xhr.setRequestHeader("site", "npssd");
                        xhr.setRequestHeader("dotype", "view");
                        xhr.responseType = 'blob';
                        xhr.onload = function () {
                            if (this.status == 200) {
                                var blob = this.response;
                                if (window.navigator && window.navigator.msSaveOrOpenBlob) {
                                    var fileName = Title + '.pdf';
                                    window.navigator.msSaveOrOpenBlob(blob, fileName);
                                } else {
                                    var fileURL = URL.createObjectURL(blob);
                                    window.open(fileURL)
                                }
                            } else {
                                layer.msg("抱歉，该文章暂无资源！");
                            }
                        };
                        xhr.send()
                    })
                }
            });
    $(elmentobj).attr("onclick", click); //执行完后再为按钮附上点击事件
}

// 预览下载和阅读方法
function AddHandleCount2(elmentobj, url, titlec) {
    var click = $(elmentobj).attr("onclick"); //获取点击事件
    $(elmentobj).attr("onclick", ""); //暂时取消点击事件,避免用户连续点击,当用户完成一次在线阅读或下载操作以后,在为该按钮附上点击事件
    if (checkLogin()) {
        var xhr = new XMLHttpRequest();
        xhr.open('get', url, true);
        xhr.responseType = 'blob';
        xhr.onload = function () {
            if (this.status == 200) {
                var blob = this.response
                var fileName = titlec + '.pdf';
                if ('download' in document.createElement('a')) {
                    //非IE下载
                    var elink = document.createElement('a');
                    elink.download = fileName;
                    elink.style.display = 'none';
                    elink.href = URL.createObjectURL(blob);
                    document.body.appendChild(elink);
                    elink.click();
                    URL.revokeObjectURL(elink.href);
                    document.body.removeChild(elink);
                } else {
                    navigator.msSaveBlob(blob, fileName);
                }
            } else {
                layer.msg("抱歉，该文章暂无资源！");
            }
        }
        xhr.send()
    } else {
        layer.msg("抱歉！请先登录才能下载和阅读。");
    }
    $(elmentobj).attr("onclick", click);
}

function ViewHandleCount2(elmentobj, url, titlec) {
    if (checkLogin()) {
        var click = $(elmentobj).attr("onclick"); //获取点击事件
        $(elmentobj).attr("onclick", ""); //暂时取消点击事件,避免用户连续点击,当用户完成一次在线阅读或下载操作以后,在为该按钮附上点击事件
        var xhr = new XMLHttpRequest();
        xhr.open('get', url, true);
        xhr.responseType = 'blob';
        xhr.onload = function () {
            if (this.status == 200) {
                var blob = this.response;
                if (window.navigator && window.navigator.msSaveOrOpenBlob) {
                    var fileName = titlec + '.pdf';
                    window.navigator.msSaveOrOpenBlob(blob, fileName);
                } else {
                    var fileURL = URL.createObjectURL(blob);
                    window.open(fileURL)
                }
            } else {
                layer.msg("抱歉，该文章暂无资源！");
            }
        };
        xhr.send()
        $(elmentobj).attr("onclick", click);
    } else {
        layer.msg("抱歉！请先登录才能下载和阅读。");
    }
};

var currentXhr = null;
var currentDownloadButton = null;
var currentDownzip = null;
var currentSiblingStates = null;
function DownloadAttachment(elmentobj, type, articleid, downzip, downrar, preview, GCH, Class, Title, ShowWriter, periodname) {
    if (checkLogin()) {
        var click = $(elmentobj).attr("onclick");
        $(elmentobj).attr("disabled", "disabled");
        $(elmentobj).addClass("btn_loading");
        $(elmentobj).text("");
        var $siblings = $(elmentobj).siblings();
        var states = [];
        $siblings.each(function() {
            states.push({
                element: this,
                display: $(this).css('display')
            });
        });
        currentSiblingStates = states;
        $siblings.hide();
        GCH = changValue2(GCH);
        Class = changValue2(Class);
        ShowWriter = changValue2(ShowWriter);
        var obj = {};
        obj.type = type;
        obj.articleid = articleid;
        obj.id = articleid;
        obj.periodname = periodname;
        obj.downzip = downzip;
        obj.downrar = downrar;
        obj.preview = preview;
        obj.gch = GCH;
        obj.class = Class;
        obj.titleC = Title;
        obj.showWriter = ShowWriter;
        obj.pageType = pageType;
        $.ajax({
            type: "POST",
            url: "/Literature/attachmentDownload",
            data: JSON.stringify(obj),
            contentType: "application/json; charset=utf-8",
            dataType: 'json',
            async: false,
            success: function (data) {
                if (data.code === 500) {
                    layer.msg(data.msg ? data.msg : "抱歉，该文章暂无资源！");
                    if (currentSiblingStates) {
                        currentSiblingStates.forEach(function(item) {
                            $(item.element).css('display', item.display);
                        });
                        currentSiblingStates = null;
                    }
                    $(elmentobj).removeClass("btn_loading");
                    $(elmentobj).attr("disabled", "");
                    $(elmentobj).siblings().show();
                    return false;
                }
                if (data.code === 501) {
                    layer.msg("抱歉，该文章暂无资源！");
                    if (currentSiblingStates) {
                        currentSiblingStates.forEach(function(item) {
                            $(item.element).css('display', item.display);
                        });
                        currentSiblingStates = null;
                    }
                    $(elmentobj).removeClass("btn_loading");
                    $(elmentobj).attr("disabled", "");
                    $(elmentobj).siblings().show();
                    return false;
                }
                const progressContainer = document.getElementById("download-progress");
                const progressBar = document.getElementById("progress-bar");
                const progressPercent = document.getElementById("progress-percentage");
                const speedDisplay = document.getElementById("speed-display");
                progressContainer.style.display = "block";
                $(".cont_head_box").css("height","220px")
                if (window.download_list) {dow_list_hei()}
                progressBar.style.width = "0%";
                progressPercent.textContent = "0%";
                speedDisplay.textContent = "0.00 MB/s";
                let lastUpdate = Date.now();
                let lastLoaded = 0;
                let estimatedTimeSec = 0;
                ms.util.getMinioSign(function (sign) {
                    var xhr = new XMLHttpRequest();
                    xhr.open('get', data.url, true);
                    xhr.setRequestHeader("sign", sign);
                    xhr.setRequestHeader("site", "npssd");
                    xhr.setRequestHeader("dotype", "down");
                    xhr.responseType = 'blob';
                    xhr.onprogress = function (event) {
                        if (event.lengthComputable) {
                            const percent = (event.loaded / event.total) * 100;
                            progressBar.style.width = percent + "%";
                            progressPercent.textContent = percent.toFixed(1) + "%";
                            const now = Date.now();
                            const timeDiff = (now - lastUpdate) / 1000;
                            const loadedDiff = event.loaded - lastLoaded;
                            if (timeDiff > 0) {
                                const speed = (loadedDiff / (1024 * 1024)) / timeDiff;
                                speedDisplay.textContent = speed.toFixed(2) + " MB/s";
                            }
                            if (event.total > 0) {
                                const remaining = (event.total - event.loaded) / (event.loaded / timeDiff / 1024 / 1024);
                                estimatedTimeSec = Math.max(0, Math.floor(remaining));
                                const minutes = Math.floor(estimatedTimeSec / 60);
                                const seconds = estimatedTimeSec % 60;
                            }
                            lastUpdate = now;
                            lastLoaded = event.loaded;
                        }
                    };
                    xhr.onload = function () {
                        if (this.status == 200) {
                            var blob = this.response
                            if (downzip == 1) {
                                var fileName = Title + '.zip';
                            } else {
                                var fileName = Title + '.rar';
                            }
                            if ('download' in document.createElement('a')) {
                                var elink = document.createElement('a');
                                elink.download = fileName;
                                elink.style.display = 'none';
                                elink.href = URL.createObjectURL(blob);
                                document.body.appendChild(elink);
                                elink.click();
                                URL.revokeObjectURL(elink.href);
                                document.body.removeChild(elink);
                            } else {
                                navigator.msSaveBlob(blob, fileName);
                            }
                            progressContainer.style.display = "none";
                            $(".cont_head_box").css("height","190px");
                            if (window.download_list) {dow_list_hei()}
                            $(elmentobj).removeClass("btn_loading");
                            $(elmentobj).attr("disabled", "");
                            if (currentSiblingStates) {
                                currentSiblingStates.forEach(function(item) {
                                    $(item.element).css('display', item.display);
                                });
                                currentSiblingStates = null;
                            }
                            if (downzip == 1) {
                                $(elmentobj).text("下载ZIP")
                            } else {
                                $(elmentobj).text("下载RAR")
                            }
                        } else {
                            layer.msg("抱歉，该文章暂无资源！");
                            if (currentSiblingStates) {
                                currentSiblingStates.forEach(function(item) {
                                    $(item.element).css('display', item.display);
                                });
                                currentSiblingStates = null;
                            }
                            $(elmentobj).removeClass("btn_loading");
                            $(elmentobj).attr("disabled", "");
                            if (downzip == 1) {
                                $(elmentobj).text("下载ZIP")
                            } else {
                                $(elmentobj).text("下载RAR")
                            }
                        }
                    }
                    xhr.onerror = function() {
                        layer.msg("下载失败，请检查网络");
                        progressContainer.style.display = "none";
                        $(".cont_head_box").css("height","190px");
                        if (window.download_list) {dow_list_hei()}
                        if (currentSiblingStates) {
                            currentSiblingStates.forEach(function(item) {
                                $(item.element).css('display', item.display);
                            });
                            currentSiblingStates = null;
                        }
                        $(elmentobj).removeClass("btn_loading");
                        $(elmentobj).attr("disabled", "");
                        if (downzip == 1) {
                            $(elmentobj).text("下载ZIP")
                        } else {
                            $(elmentobj).text("下载RAR")
                        }
                    };
                    currentXhr = xhr;
                    currentDownloadButton = elmentobj;
                    currentDownzip = downzip;
                    xhr.send()
                });
            }
        });
        $(elmentobj).attr("onclick", click);
    } else {
        layer.msg("抱歉！请先登录才能下载和阅读。");
    }
}
// 动态调整下载框高度
function dow_list_hei(){
    var contentHeight = $('#myLayerContent').outerHeight();
    var maxHeight = 600; // 设定最大高度
    if (contentHeight > maxHeight) {
        layer.style(window.download_list, {
            height: maxHeight + 'px'
        });
        $('#myLayerContent').css({
            'overflow-y': 'auto',
            'max-height': maxHeight + 'px'
        });
    } else {
        layer.style(window.download_list, {
            height: contentHeight + 'px'
        });
    };
};

function close_down_list(){
    if (currentXhr) {
        currentXhr.abort();
        const progressContainer = document.getElementById("download-progress");
        if (currentDownloadButton) {
            progressContainer.style.display = "none";
            $(".cont_head_box").css("height","190px");
            if (window.download_list) {dow_list_hei()}
            $(currentDownloadButton).removeClass("btn_loading");
            $(currentDownloadButton).attr("disabled", "");
            if (currentSiblingStates) {
                currentSiblingStates.forEach(function(item) {
                    $(item.element).css('display', item.display);
                });
                currentSiblingStates = null;
            }
            if (currentDownzip == 1) {
                $(currentDownloadButton).text("下载ZIP");
            } else {
                $(currentDownloadButton).text("下载RAR");
            }
        }
        currentXhr = null;
        currentDownloadButton = null;
        currentDownzip = null;
    }
}

//习文库pdf阅读
function xwkPdfRead(elmentobj, url, Title) {
    var click = $(elmentobj).attr("onclick"); //获取点击事件
    $(elmentobj).attr("onclick", ""); //暂时取消点击事件,避免用户连续点击,当用户完成一次在线阅读或下载操作以后,在为该按钮附上点击事件
    if (checkLogin()) {
        $.ajax({
            type: "GET",
            url: url,
            contentType: "application/json; charset=utf-8",
            async: false,
            success: function (onedata) {
                if (changValue2(onedata.msg)) {
                    layer.msg(onedata.msg);
                    return false;
                }
                var userId = userInfo.userId;
                ms.util.getMinioSign(function (sign) {
                    var xhr = new XMLHttpRequest();
                    xhr.open('get', onedata.url, true);
                    xhr.setRequestHeader("sign", sign);
                    xhr.setRequestHeader("userInfo", userId);
                    xhr.setRequestHeader("site", "npssd");
                    xhr.setRequestHeader("dotype", "view");
                    xhr.responseType = 'blob';
                    xhr.onload = function () {
                        if (this.status == 200) {
                            var blob = this.response;
                            if (window.navigator && window.navigator.msSaveOrOpenBlob) {
                                var fileName = Title + '.pdf';
                                window.navigator.msSaveOrOpenBlob(blob, fileName);
                            } else {
                                var fileURL = URL.createObjectURL(blob);
                                window.open(fileURL)
                            }
                        } else {
                            layer.msg("抱歉，该文章暂无资源！");
                        }
                    };
                    xhr.send()
                })
            }
        });
    } else {
        layer.msg("抱歉！请先登录才能下载和阅读。");
    }
    $(elmentobj).attr("onclick", click); //执行完后再为按钮附上点击事件
}

//全文下载
function xwkPdfDown(elmentobj, url, Title) {
    var click = $(elmentobj).attr("onclick"); //获取点击事件
    $(elmentobj).attr("onclick", ""); //暂时取消点击事件,避免用户连续点击,当用户完成一次在线阅读或下载操作以后,在为该按钮附上点击事件
    if (checkLogin()) {
        $.ajax({
            type: "GET",
            url: url,
            contentType: "application/json; charset=utf-8",
            async: false,
            success: function (onedata) {
                if (changValue2(onedata.msg)) {
                    layer.msg(onedata.msg);
                    return false;
                }
                var userId = userInfo.userId;
                ms.util.getMinioSign(function (sign) {
                    var xhr = new XMLHttpRequest();
                    xhr.open('get', onedata.url, true);
                    xhr.setRequestHeader("sign", sign);
                    xhr.setRequestHeader("userInfo", userId);
                    xhr.setRequestHeader("site", "npssd");
                    xhr.setRequestHeader("dotype", "down");
                    xhr.responseType = 'blob';
                    xhr.onload = function () {
                        if (this.status == 200) {
                            var blob = this.response
                            var fileName = Title + '.pdf';
                            if ('download' in document.createElement('a')) {
                                //非IE下载
                                var elink = document.createElement('a');
                                elink.download = fileName;
                                elink.style.display = 'none';
                                elink.href = URL.createObjectURL(blob);
                                document.body.appendChild(elink);
                                elink.click();
                                URL.revokeObjectURL(elink.href);
                                document.body.removeChild(elink);
                            } else {
                                navigator.msSaveBlob(blob, fileName);
                            }
                        } else {
                            layer.msg("抱歉，该文章暂无资源！");
                        }
                    }
                    xhr.send();
                })
            }
        });
    } else {
        layer.msg("抱歉！请先登录才能下载和阅读。");
    }
    $(elmentobj).attr("onclick", click); //执行完后再为按钮附上点击事件
}

// function getExplain(){
//     $.ajax({
//         type: "GET",
//         url: "/Literature/getIndexPdf",
//         contentType: "application/json; charset=utf-8",
//         async: false,
//         success: function (onedata) {
//             if (changValue2(onedata.msg)) {
//                 layer.msg(onedata.msg);
//                 return false;
//             }
//             var userId = userInfo.userId;
//             var xhr = new XMLHttpRequest();
//             xhr.open('get', onedata.url, true);
//             xhr.setRequestHeader("sign", ms.util.getMinioSign());
//             xhr.setRequestHeader("userInfo",userId);
//             xhr.setRequestHeader("site","npssd");
//             xhr.setRequestHeader("dotype","view");
//             xhr.responseType = 'blob';
//             xhr.onload = function() {
//                 if (this.status == 200) {
//                     var blob = this.response;
//                     if (window.navigator && window.navigator.msSaveOrOpenBlob) {
//                         var fileName = '国家哲学社会科学文献中心平台切换浏览器常见问题说明.pdf';
//                         window.navigator.msSaveOrOpenBlob(blob,fileName);
//                     }else{
//                         var fileURL = URL.createObjectURL(blob);
//                         window.open(filterXSS(fileURL))
//                     }
//                 } else {
//                     layer.msg("抱歉，该文章暂无资源！");
//                 }
//             };
//             xhr.send()
//         }
//     });
// }

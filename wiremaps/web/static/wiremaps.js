$(document).ready(function() {
    if ($("div#message").css("position") != "fixed") {
	// Should be this jerk of IE
	$("div#message").css("position", "absolute");
    }
    $("div#message").bind("click", hideMessage);
    $("div#search form").bind("submit", function(event) {
        event.preventDefault();
        search($("div#search form input[name=search]").val());
    });
    $("div#searchactions a").bind("click", function(event) {
        event.preventDefault();
	$("div#searchresults").hide();
    });
    $("div#vlanactions a").bind("click", function(event) {
        event.preventDefault();
	$("div#infovlans").hide();
	$("div#actions #vlans").show();
    });
    $("form")
	.bind("submit", function() {
		  return false;
	});
    $("div#equipments select")
	.bind("change", function(event) {
	    event.preventDefault();
	    $.historyLoad(this.value.split(" - ")[1]);
	});
    $("div#actions #details a")
	.bind("click", function(event) {
	    event.preventDefault();
   	    $("table#ports tbody tr").not(".expanded").children("td.name").click();
	    $(this).parent().hide();
	});
    $("div#actions #vlans a").bind("click", showVlans);
    $("div#actions #autosearch a").bind("click", searchOrShow);
    $("div#actions #refresh a").bind("click", refresh);
    /* Unhide application on load */
    $("div#search").css("visibility", "visible");
    $("div#application").css("visibility", "visible");
    $("div#search input#search").autocomplete("complete",
					      {minChars: 3,
					       onItemSelect: function(li) {
						 $("div#search form").submit();
					       }});
    hideMessage();
    loadEquipments();
    $.historyInit(loadHistory);
});

var sortInProgress = false;
function sortTable()
{
  if (sortInProgress) {
    return;
  }
  sortInProgress = true;
  setTimeout(function() {
    $("table#ports").unbind();
    $("table#ports thead th").unbind();
    $("table#ports").tablesorter({
      textExtraction: function(node) {
	if ($(node).hasClass("name")) {
	  var val = $(node).parent().attr("_index");
	  if (val != null) {
	    return val;
	  }
	}
	if ($(node).hasClass("state")) {
	  return $(node).children("img").attr("alt");
	}
	if ($(node).children("span.sortable").size() == 1)
	  return $(node).children("span.sortable").html();
	return $(node).html();
      }
    });
    sortInProgress = false;
  }, 300);
}

function loadEquipments()
{
    sendMessage("info", "Loading list of equipments...");
    $.ajax({type: "GET",
	    cache: false,
	    url: "equipment/",
	    dataType: "json",
	    error: function(xmlh, textstatus, error) {
		sendMessage("alert", "Unable to get the list of equipments");
	    },
	    success: function(data) {
		$("div#equipments select")
		    .append( function(data) {
				 return $.map(data, function(x) {
					   return "<option "+
						      " _ip='"+x[1]+
						      "' _hostname='"+x[0]+
						      "'>"+x.join(" - ")+"</option>";
				       }).join("\n");
			     }(data) );
	        cur = $("div#photo img").attr("src").split("/")[1];
		if (cur)
		  selectEquipment(cur);
		hideMessage();
	    }});
}

function selectEquipment(ip)
{
    $("div#equipments select option")
      .each(function() {
	      tip = this.text.split(" - ")[1];
	      if (ip == tip) {
		this.selected = true;
		return;
	      }
	    });
}

function loadHistory(hash)
{
  if (hash) {
    selectEquipment(hash);
    loadEquipment(hash);
  }
}

function loadEquipment(ip)
{
    $("div#equipments select")
	.children(".first:first").remove();
    $("div#equipments div#actions").css("visibility", "visible");
    $("div#photo img")
	.attr("src", "images/" + ip)
	.parent().show();
    $("div#actions a").attr("href", "search/" + ip + "/");
    $("table#ports").hide();
    $("div#infovlans").hide();
    $.ajax({type: "GET",
	    cache: false,
	    url: "equipment/"+ip+"/descr/",
	    dataType: "json",
	    error: function(xmlh, textstatus, error) {
		$("div#description").hide();
	    },
	    success: function(data) {
	        $("div#description").html(data[0][0]);
		$("div#description").show();
		hideMessage();
	    }});
    sendMessage("info", "Loading list of ports for "+ip);
    $.ajax({type: "GET",
	    cache: false,
	    url: "equipment/"+ip+"/",
	    dataType: "json",
	    error: function(xmlh, textstatus, error) {
		sendMessage("alert", "Unable to get the list of ports for "+ip);
	    },
	    success: function(data) {
		replacePorts(data);
		$("table#ports").show();
		$("div#actions #details").show();
		$("div#actions #vlans").show();
		hideMessage();
	        $(document).scrollTop($("div#application").offset().top);
	    }});
}

function showVlans(event)
{
  event.preventDefault();
  var target = $(this).attr("href").match(/.*\/([^\/]+)[\/]?/);
  var ip = target[1];
  sendMessage("info", "Loading vlan information for "+ip);
  $.ajax({type: "GET",
	  cache: false,
	  url: "equipment/"+ip+"/vlans/",
	  dataType: "html",
	  error: function(xmlh, textstatus, error) {
		$("div#infovlans").hide();
		sendMessage("alert", "Unable to get the list of vlans for "+ip);
	  },
	  success: function(data) {
	    $("div#vlancontent").html(data);
	    $("div#vlancontent").find("a").bind("click", searchOrShow);
	    $("div#infovlans").show();
	    $("div#actions #vlans").hide();
	    hideMessage();
	  }});
}

function displayPortDetails(event)
{
  event.preventDefault();
  var port = $(this).parent();
  port.addClass("expanded");
  var ip = $("div#photo img")
	     .attr("src").match(/.*\/([0-9.]+)$/)[1];
  port.find("td.state").addClass("loading");
  $.ajax({type: "GET",
	  cache: false,
	  url: "equipment/"+ip+"/"+port.attr("_index")+"/",
	  dataType: "json",
	  error: function(xmlh, textstatus, error) {
	    sendMessage("alert",
	                "Unable to get detailed info for port " + port.find("td.name a").text());
	  },
	  success: function(data) {
	    displayPortInformation(port, data);
	  }});
}

function hidePortDetails(event)
{
  event.preventDefault();
  var port = $(this).parent();
  port.removeClass("expanded");
  port.children(":gt(2)").html("");
}

function replacePorts(ports)
{
    var portRows = $("table#ports > tbody");
    var portReference = portRows.children(":first");
    $("table#ports > thead th:gt(2)").remove();
    portReference.removeClass("expanded")
      .hide()
      .children(":gt(2)").remove();
    portRows.children(":not(:first)").remove();
    for (var i = 0; i < ports.length; i++) {
	var port = portReference.clone().appendTo("table#ports > tbody");
	var speed = ports[i][4];
	if ([10, 100, 1000, 10000].indexOf(speed) == -1)
	  speed = null;
	port
	  .children("td.name").toggle(displayPortDetails, hidePortDetails).end()
	  .find("td.state img")
	    .attr("src","static/port-"+ports[i][3]+
		  "-"+speed+"-"+ports[i][5]+
		  "-"+ports[i][6]+".png")
	    .attr("alt", ports[i][3]+" "+speed+" "+ports[i][5])
	    .end()
	  .find("td.name a").html(ports[i][1]).end()
	  .attr("_index", ports[i][0]);
	if (ports[i][2] === null)
	  port.find("td.description").html("");
	else
	  port.find("td.description").html(ports[i][2]);
    }
    if (ports.length > 0) {
      portReference.remove();
    }
    portRows.children().show();
    sortTable();
}


function displayPortInformation(port, data) {
    for (var i = 0; i < data.length; i++) {
      var column = data[i][0];
      var html = data[i][1];
      var sort = data[i][2];
      // Does the column already exists?
      var columns = $("table#ports thead th");
      var found = false;
      var index = 3;		// Skip first children
      while (index < columns.size()) {
	if (columns.eq(index).text() == column) {
	  found = true;
	  break;
	}
	if (columns.eq(index).text() > column) {
	  index--;
	  break;
	}
	index++;
      }
      if (index == columns.size())
	index--;
      if (!found) {
	// We need to insert a new column at this index
	index++;
	$("#ports > thead > tr > th:nth-child("+index+")")
	  .after("<th>"+column+"</th>");
	$("#ports > tbody > tr > td:nth-child("+index+")")
	  .after("<td class='column'></td>");
      }
      port.children().eq(index).html(html);
      if (sort != null) {
	var s = $(document.createElement("span"));
	s.attr("class", "sortable");
	s.text(sort);
	s.appendTo(port.children().eq(index));
      }
    }
    port.find("td.column a").bind("click", searchOrShow);
    port.find("td.state").removeClass("loading");
    sortTable();
}

function displaySearchResults(data, elt) {
    var ul = $("div#searchresults ul.searchresults");
    ul.children().remove();
    $("div#searchresults span.data:first").html(elt);
    for (var i = 0; i < data.length; i++) {
	ul.append("<li>"+data[i]+"</li>");
    }
    ul.find("a").bind("click", searchOrShow);
    $("div#searchresults").show();
    hideMessage();
    $(document).scrollTop($("div#searchresults").offset().top);
}

function searchOrShow(event) {
    event.preventDefault();
    var target = $(this).attr("href").match(/.*\/([^\/]+)[\/]?/);
    if (target[0].match(/^search/))
	search(target[1]);
    else if (target[0].match(/equipment/)) {
	var a = $("div#equipments select option").filter(function() {
		    return (($(this).attr("_ip") == target[1]) ||
			    ($(this).attr("_hostname").toLowerCase() == target[1].toLowerCase())); });
	if (a.length == 0) {
	    sendMessage("alert", "Unable to find equipment, please reload");
	    return;
	}
	a.attr("selected", 1).parent().change();
    } else
	sendMessage("alert", "Unknown link: " + target[0]);
}

function refresh(event) {
    event.preventDefault();
    var target = $(this).attr("href").match(/.*\/([^\/]+)[\/]?/);
    sendMessage("info", "Refreshing "+target[1]+"...");
    $.ajax({type: "GET",
	    cache: false,
	    url: "equipment/"+target[1]+"/refresh/",
	    dataType: "json",
	    error: function(xmlh, textstatus, error) {
		sendMessage("alert",
		"Unable to refresh "+target[1]);
	    },
	    success: function(data) {
		    if (data["status"] == 0) {
			sendMessage("alert", "Refresh error: "+data["message"]);
		    } else {
			sendMessage("ok", "Refresh successful");
			loadEquipment(target[1]);
		    }
	    }});
}

function search(elt) {
    sendMessage("info", "Search for "+elt+"...");
    $.ajax({type: "GET",
	    cache: false,
	    url: "search/"+elt+"/",
	    dataType: "json",
	    error: function(xmlh, textstatus, error) {
		sendMessage("alert",
		"Unable to get search results");
	    },
	    success: function(data) {
		displaySearchResults(data, elt);
	    }});
}

function sendMessage(level, msg) {
    $("div#message")
	.stop()
	.filter(":not(hidden)")
	    .hide()
	.end()
	.children("div")
	    .removeClass()
	    .addClass("msg"+level)
	    .html(msg)
	.end()
	.css("top", "-1px")
	.show();
}

function hideMessage()
{
    $("div#message:not(hidden)")
	.stop()
	.animate({"top": "-32px"}, "slow", undefined, function() {
		     $("div#message:not(hidden)").fadeOut("fast");
		 });
}

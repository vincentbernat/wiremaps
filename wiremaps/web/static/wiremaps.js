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
    $("form")
	.bind("submit", function() {
		  return false;
	});
    $("div#equipments select")
	.bind("change", function(event) {
	    event.preventDefault();
	    loadEquipment(this.value.split(" - ")[1]);
	});
    $("div#actions #details a")
	.bind("click", function(event) {
	    event.preventDefault();
	    $("div#ports div.portdetails:hidden")
		      .parent().find(".portbasics").click();
	    $(this).parent().hide();
	});
    $("div#actions #autosearch a").bind("click", searchOrShow);
    $("div#actions #refresh a").bind("click", refresh);
    /* Unhide application on load */
    $("div#search").css("visibility", "visible");
    $("div#application").css("visibility", "visible");
    hideMessage();
    loadEquipments();
});

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
					   return "<option _ip='"+x[1]+
						      "' _hostname='"+x[0]+
						      "'>"+x.join(" - ")+"</option>";
				       }).join("\n");
			     }(data) );
		hideMessage();
	    }});
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
    $("div#ports").hide();
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
		$("div#ports").show();
		$("div#actions #details").show();
		hideMessage();
	    }});
}

function displayPortDetails(event)
{
    // "this" should be a .portexpand
    event.preventDefault();
    var port = $(this).find("li.portexpand").attr("_index");
    var portdetails = $(this).parent()
	.find("div.portdetails");
    var ip = $("div#photo img")
	.attr("src").match(/.*\/([0-9.]+)$/)[1];
    portdetails.find("li").remove();
    $.ajax({type: "GET",
	    cache: false,
	    url: "equipment/"+ip+"/"+port+"/",
	    dataType: "json",
	    error: function(xmlh, textstatus, error) {
		sendMessage("alert",
		"Unable to get detailed info for port " + port);
	    },
	    success: function(data) {
		displayPortInformation(portdetails, data);
	    }});
}

function replacePorts(ports)
{
    var portUl = $("div#ports > ul");
    var portReference = portUl.children(":first");
    portReference.hide();
    portUl.children(":not(:first)").remove();
    for (var i = 0; i < ports.length; i++) {
	var port = portReference.clone().appendTo("div#ports > ul");
	port
	    .removeClass("up").removeClass("down")
	    .addClass(ports[i][3])
	    .find("div.portname").html(ports[i][1]).end()
	    .find("div.portactions .portexpand")
		.attr("_index", ports[i][0]).parents("div.portbasics")
		.toggle(displayPortDetails,
			function(event) {
			    event.preventDefault();
			    $(this).parent().find("div.portdetails")
				.hide();
			});
	if (ports[i][2] === null)
	    port.find("div.portalias").hide();
	else
	    port.find("div.portalias").html(ports[i][2]).show();
    }
    portUl.find("div.portdetails").hide();
    portUl.children(":not(:first)").show();
}

function displayPortInformation(portdetails, data) {
    var ul = portdetails.children("ul");
    for (var i = 0; i < data.length; i++) {
	ul.append("<li>"+data[i]+"</li>");
    }
    portdetails.find("a").bind("click", searchOrShow);
    portdetails.show();
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
}

function searchOrShow(event) {
    event.preventDefault();
    var target = $(this).attr("href").match(/.*\/([^\/]+)[\/]?/);
    if (target[0].match(/^search/))
	search(target[1]);
    else if (target[0].match(/equipment/)) {
	var a = $("div#equipments select option").filter(function() {
		    return (($(this).attr("_ip") == target[1]) ||
			    ($(this).attr("_hostname") == target[1])); });
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

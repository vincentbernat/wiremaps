/**
*    Json key/value autocomplete for jQuery
*    Provides a transparent way to have key/value autocomplete
*    Copyright (C) 2008 Ziadin Givan www.CodeAssembly.com
*    Simplified by Vincent Bernat <bernat@luffy.cx>
*
*    This program is free software: you can redistribute it and/or modify
*    it under the terms of the GNU Lesser General Public License as published by
*    the Free Software Foundation, either version 3 of the License, or
*    (at your option) any later version.
*
*    This program is distributed in the hope that it will be useful,
*    but WITHOUT ANY WARRANTY; without even the implied warranty of
*    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
*    GNU General Public License for more details.
*
*    You should have received a copy of the GNU Lesser General Public License
*    along with this program.  If not, see http://www.gnu.org/licenses/
*/
jQuery.fn.autocomplete = function(url, settings )
{
	return this.each( function()//do it for each matched element
	{
		//this is the original input
		var textInput = $(this);
		textInput.attr('autocomplete', 'off');
		textInput.after('<ul class="autocomplete"></ul>');
		var list = textInput.next();
		var oldText = '';
		var typingTimeout;
		var size = 0;
		var selected = 0;

		settings = jQuery.extend(//provide default settings
		{
			minChars: 3,
			timeout: 300
		} , settings);

		function getData(text)
		{
			window.clearInterval(typingTimeout);
			if (text != oldText && (settings.minChars != null &&
						text.length >= settings.minChars))
			{
				clear();
				textInput.addClass('autocomplete-loading');
				$.getJSON(url + "/" + encodeURI(text) + "/",
					  function(data)
				{
					var items = '';
					if (data)
					{
						size = data.length;
						for (i = 0; i < data.length; i++)//iterate over all options
						  items += '<li>' + data[i] + '</li>';
						list.html(items);
						list.css({top: textInput.offset().top +
							  textInput.outerHeight(),
							  left: textInput.offset().left,
							  width: textInput.width()});
						list.show().children()
						  .hover(function() {
							$(this).addClass("selected").siblings()
							  .removeClass("selected");
						      }, function() {
							$(this).removeClass("selected");
						      })
						  .click(function () {
							   textInput.val($(this).text());
							   textInput.parents("form").submit();
							   clear(); });
					}
					textInput.removeClass('autocomplete-loading');
				});
				oldText = text;
			}
		}

		function clear()
		{
			list.hide();
			size = 0;
			selected = 0;
		}

		textInput.keydown(function(e) {
			window.clearInterval(typingTimeout);
			if ((e.which == 27) || (e.which == 46) ||
			    (e.which == 8) || (e.which == 13)) //escape, delete, backspace or enter
			  clear();
			else if ((e.which == 40) || (e.which == 9) || (e.which == 38)) //move up, down
			{
			  switch(e.which)
			  {
				case 40:
				case 9:
				  selected = selected >= size - 1 ? 0 : selected + 1; break;
				case 38:
				  selected = selected <= 0 ? size - 1 : selected - 1; break;
				default: break;
			  }
			  //set selected item and input values
			  textInput.val(list.children()
					.removeClass('selected')
					.eq(selected)
					.addClass('selected').text() );
			} else {
			  typingTimeout = window.setTimeout(function() { getData(textInput.val()); },
							    settings.timeout);
			}
			return true;
		});
	});
};

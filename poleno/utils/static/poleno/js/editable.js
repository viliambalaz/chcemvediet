/* Required for ``poleno.utils.forms.EditableSpan`` form widget.
 */

$(function(){
	function repeat(s, n) {
		var r = '';
		while (n > 0) {
			if (n & 1) r += s;
			n >>= 1;
			s += s;
		}
		return r;
	}
	function getContent(element) {
		var e = $('<pre/>').html(element.html());
		e.find('div, p').replaceWith(function(){ return this.innerHTML + '\n'; });
		e.find('br').replaceWith('\n');
		var t = e.text();
		if (t && t[t.length-1] === '\n') t = t.slice(0, -1);
		t = t.replace(/\n[^\S\n]*/g, '\n        ');
		return t;
	}
	function update(element) {
		var content = getContent(element);
		var padding = content.match(/\n\s*$/) ? 0 : content.length < 10 ? 47 : 5
		element.attr('data-padding', repeat('. ', padding));
		element.next().val(content);
		element.html(content);
	}
	function updateAll() {
		$('.pln-editable-span').each(function(){
			update($(this));
		});
	}

	$(document).on('blur', '.pln-editable-span', function(){
		update($(this));
	});
	$(document).on('focusin', '.pln-editable-container', function(){
		$(this).addClass('focus');
	});
	$(document).on('focusout', '.pln-editable-container', function(){
		$(this).removeClass('focus');
	});
	$(document).on('pln-dom-changed', function(){ // Triggered by: poleno/js/ajax.js
		updateAll();
	});
	updateAll();
});

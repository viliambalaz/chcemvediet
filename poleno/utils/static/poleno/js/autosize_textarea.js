/* Enables textarea to automatically adjust its height to its content.
 *
 * Requires:
 *  -- JQuery
 *
 * Example:
 *     <textarea class="pln-autosize"></textarea>
 */
$(function(){
	function autosize(){
		$(this).css({
			'height': 'auto',
			'overflow-y': 'hidden',
		});
		var lineHeight = parseFloat($(this).css('line-height'));
		var paddingHeight = $(this).innerHeight() - $(this).height();
		var contentHeight = this.scrollHeight - paddingHeight;
		var computedHeight = Math.ceil(contentHeight / lineHeight) * lineHeight;
		$(this).height(computedHeight);

	};
	function autosizeAll(){
		$('textarea.pln-autosize').each(autosize);
	};
	$(document).on('input', 'textarea.pln-autosize', autosize);
	$(document).on('pln-dom-changed', autosizeAll); // Triggered by: poleno/js/ajax.js
	$(window).on('resize', autosizeAll);
	autosizeAll();
});

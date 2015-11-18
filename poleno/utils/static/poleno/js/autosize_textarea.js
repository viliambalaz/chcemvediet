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
		var computedLines = Math.max(3, Math.ceil(contentHeight / lineHeight));
		var computedHeight = computedLines * lineHeight;
		console.log(lineHeight, paddingHeight, contentHeight, computedHeight);
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

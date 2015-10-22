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
		}).height(this.scrollHeight);
	};
	function autosizeAll(){
		$('textarea.pln-autosize').each(autosize);
	};
	$(document).on('input', 'textarea.pln-autosize', autosize);
	$(document).on('pln-dom-changed', autosizeAll); // Triggered by: poleno/js/ajax.js
	$(window).on('resize', autosizeAll);
	autosizeAll();
});

/* Enabled Bootstrap tooltips for elements with ``pln-with-tooltip`` class.
 *
 * Requires:
 *  -- JQuery
 *  -- Bootstrap 2
 *
 * Example:
 *     <a class="pln-with-tooltip" href="..." data-toggle="tooltip" title="Tooltip content.">Go</a>
 */
$(function(){
	function tooltip(base){
		$(base).find('.pln-with-tooltip').not('.hasTooltip').addClass('hasTooltip').each(function(){
			if ($(this).hasClass('tooltip-permanent')) {
				$(this).tooltip({trigger: 'manual'}).tooltip('show');
			} else {
				$(this).tooltip();
			}
		});
	};
	$(document).on('pln-dom-changed', function(event){ // Triggered by: poleno/js/ajax.js
		tooltip(event.target);
	});
	tooltip(document);
});

/* Clicking on elements with class ``pln-print`` prints element specified by ``data-target``
 * attribute.
 *
 * Requires:
 *  -- JQuery
 *  -- JQuery PrintArea
 *
 * Example:
 *     <button type="button" class="pln-print" data-target="#print-area">Print</button>
 *     <div id="#print-area">...</div>
 */
$(function(){
	$(document).on('click', '.pln-print', function(event){
		event.preventDefault();
		var target = $(this).data('target');
		$(target).printArea();
	});
});

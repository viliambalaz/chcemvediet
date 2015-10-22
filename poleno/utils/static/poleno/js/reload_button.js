/* Clicking on element with class ``pln-reload`` reloads the page.
 *
 * Requires:
 *  -- JQuery
 *
 * Example:
 *     <button type="button" class="pln-reload">Reload</button>
 */
$(function(){
	$(document).on('click', '.pln-reload', function(event){
		event.preventDefault();
		location.reload();
	});
});

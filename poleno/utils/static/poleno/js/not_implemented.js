/* Show not implemented alert if a user clicks on a not implemented link or sumbits a non
 * implemented form.
 *
 * Requires:
 *  -- JQuery
 *
 * Example:
 *     <a class="pln-not-implemented" href="#">Link</a>
 *     <form class="pln-not-implemented" action="#">...</form>
 */
$(function(){
	function inform(){
		window.alert('Prepáčte, ale táto operácia ešte nie je implementovaná. Pracujeme na tom.');
	};
	$(document).on('click', 'a.pln-not-implemented', function(event){
		event.preventDefault();
		inform();
	});
	$(document).on('submit', 'form.pln-not-implemented', function(event){
		event.preventDefault();
		inform();
	});
});

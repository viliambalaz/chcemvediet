/* Attaches ObligeeWidget to JQuery Autocomplete events and updates Obligee details whenever the
 * user selects a new Obligee.
 *
 * Requires:
 *  -- JQuery UI Autocomplete
 */
$(function(){
	function handler(event, ui){
		if (ui.item) {
			var obligee = ui.item.obligee;
			$('.obligee_widget_street', this).text(obligee.street);
			$('.obligee_widget_zip', this).text(obligee.zip);
			$('.obligee_widget_city', this).text(obligee.city);
			$('.obligee_widget_email', this).text(obligee.emails);
			$('.obligee_widget_details', this).show();
		} else {
			$('.obligee_widget_details', this).hide();
		}
	}
	$(document).on('autocompleteselect', '.obligee_widget', handler);
	$(document).on('autocompletechange', '.obligee_widget', handler);
});

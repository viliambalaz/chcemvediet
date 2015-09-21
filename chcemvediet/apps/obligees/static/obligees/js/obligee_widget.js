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
	$(document).on('autocompleteselect', '.obligee_widget_input', handler);
	$(document).on('autocompletechange', '.obligee_widget_input', handler);
});

/* Adds and removes widgets to/from MultipleObligeeWidget.
 *
 * Requires:
 *  -- JQuery UI Autocomplete
 */
$(function(){
	function add(container){
		var inputs = container.find('.obligee_widget_inputs');
		var skel = container.find('.obligee_widget_skel');
		var clone = skel.children().clone();
		var input = clone.find('input');
		input.attr('name', input.data('name'));
		clone.appendTo(inputs);
	}
	function del(input){
		var container = input.closest('.obligee_widget');
		var inputs = input.closest('.obligee_widget_inputs');
		input.remove();
		if (inputs.find('.obligee_widget_input').length == 0) {
			add(container);
		}
	}
	function handle_add(event){
		event.preventDefault();
		add($(this).closest('.obligee_widget'));
	}
	function handle_del(event){
		event.preventDefault();
		del($(this).closest('.obligee_widget_input'));
	}

	$(document).on('click', '.obligee_widget_add', handle_add);
	$(document).on('click', '.obligee_widget_del', handle_del);
});

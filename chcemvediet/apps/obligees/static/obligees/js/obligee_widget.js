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
			$('.chv-obligee-widget-street', this).text(obligee.street);
			$('.chv-obligee-widget-zip', this).text(obligee.zip);
			$('.chv-obligee-widget-city', this).text(obligee.city);
			$('.chv-obligee-widget-email', this).text(obligee.emails);
			$('.chv-obligee-widget-details', this).show();
		} else {
			$('.chv-obligee-widget-details', this).hide();
		}
	}
	$(document).on('autocompleteselect', '.chv-obligee-widget-input', handler);
	$(document).on('autocompletechange', '.chv-obligee-widget-input', handler);
});

/* Adds and removes widgets to/from MultipleObligeeWidget.
 *
 * Requires:
 *  -- JQuery UI Autocomplete
 */
$(function(){
	function add(container){
		var inputs = container.find('.chv-obligee-widget-inputs');
		var skel = container.find('.chv-obligee-widget-skel');
		var clone = skel.children().clone();
		var input = clone.find('input');
		input.attr('name', input.data('name'));
		clone.appendTo(inputs);
	}
	function del(input){
		var container = input.closest('.chv-obligee-widget');
		var inputs = input.closest('.chv-obligee-widget-inputs');
		input.remove();
		if (inputs.find('.chv-obligee-widget-input').length == 0) {
			add(container);
		}
	}
	function handle_add(event){
		event.preventDefault();
		add($(this).closest('.chv-obligee-widget'));
	}
	function handle_del(event){
		event.preventDefault();
		del($(this).closest('.chv-obligee-widget-input'));
	}

	$(document).on('click', '.chv-obligee-widget-add', handle_add);
	$(document).on('click', '.chv-obligee-widget-del', handle_del);
});

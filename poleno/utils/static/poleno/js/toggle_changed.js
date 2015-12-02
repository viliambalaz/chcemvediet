/* Enables input elements to automatically toggle other elemets when their value change. Tested on
 * checkbox, radio and select. But should work on all input elements as well. Toggled elements may
 * be hidden or disabled.
 *
 * Requires:
 *  -- JQuery
 *
 * Examples:
 *     <input type="checkbox" class="pln-toggle-changed" data-container="form"
 *            data-hide-target-true=".visible-if-true"
 *            data-hide-target-false=".visible-if-false" />
 *
 *     <select class="pln-toggle-changed" data-container="form"
 *             data-disable-target-aaa=".visible-if-aaa"
 *             data-disable-target-bbb=".visible-if-bbb">
 *       <option value="aaa">...</option>
 *       <option value="bbb">...</option>
 *     </select>
 *
 *     <input type="radio" name="group" value="1" class="pln-toggle-changed" data-container="form"
 *            data-target-1=".visible-if-1" data-target-2=".visible-if-2" />
 *     <input type="radio" name="group" value="2" class="pln-toggle-changed" data-container="form"
 *            data-target-1=".visible-if-1" data-target-2=".visible-if-2" />
 */
$(function(){
	function toggle(){
		var container = $(this).data('container') || 'html';
		var value = $(this).is(':checkbox') ? $(this).prop('checked') : $(this).val();

		// Toggle Hide
		var active = $(this).attr('data-hide-target-' + value);
		var all = $.map(this.attributes, function(attr){
			if (attr.name.match("^data-hide-target-")) return attr.value;
		}).join(', ');
		$(this).closest(container).find(all).not(active).hide();
		$(this).closest(container).find(active).show();

		// Toggle Disable
		var active = $(this).attr('data-disable-target-' + value);
		var all = $.map(this.attributes, function(attr){
			if (attr.name.match("^data-disable-target-")) return attr.value;
		}).join(', ');
		$(this).closest(container).find(all).not(active).prop('disabled', true);
		$(this).closest(container).find(active).prop('disabled', false);
	}
	function toggleAll(){
		// Every radio group shlould be initialized only once. If there is a checked button
		// in the group, use this button. If there is no checked button in the group use
		// any group button.
		var checked = {};
		var unchecked = {};
		$('.pln-toggle-changed:radio').each(function(){
			if ($(this).prop('checked')) {
				checked[this.name] = this;
				delete unchecked[this.name];
			} else if (!checked[this.name]) {
				unchecked[this.name] = this;
			}
		});
		$.each(checked, toggle);
		$.each(unchecked, toggle);

		// Other input elements
		$('.pln-toggle-changed:not(:radio)').each(toggle);
	}
	$(document).on('change', '.pln-toggle-changed', toggle);
	$(document).on('pln-dom-changed', toggleAll); // Triggered by: poleno/js/ajax.js
	toggleAll();
});

/* Required for ``poleno.utils.forms.CompositeText`` form widget.
 */
$(function(){
	$(document).on('focusin', '.pln-composite-text', function(){
		$(this).addClass('pln-composite-text-focus');
	})
	$(document).on('focusout', '.pln-composite-text', function(){
		$(this).removeClass('pln-composite-text-focus');
	})
});

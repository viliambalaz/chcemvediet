$(function(){
	// Fix dropdown menu panel not to close when clicked.
	$('body').on('click', '.chv-dropdown-panel', function(event){
		event.stopPropagation();
	});
});

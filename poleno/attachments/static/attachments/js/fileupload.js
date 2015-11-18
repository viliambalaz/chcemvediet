$(function(){
	function fileupload(base){
		var inputs = $(base).find('.pln-attachments input[type=file]');
		inputs.not('.hasFileupload').addClass('hasFileupload').each(function(){
			$(this).fileupload({
				dataType: 'json',
				singleFileUploads: false,
				formData: {'csrfmiddlewaretoken': $.cookie('csrftoken')},
			});
		});
	};
	$(document).on('fileuploaddone', '.pln-attachments', function(event, data){
		var container = $(this);
		var field = $(container.data('field'));
		var skel = container.find('.pln-attachments-skel');
		var list = container.find('.pln-attachments-list');
		data.result.files.forEach(function(file){
			var attachment = $(skel.html());
			attachment.data('attachment', file.pk);
			attachment.find('a').attr('href', file.url).html(file.name);
			list.append(attachment).append(' ');
			field.val(field.val() + ',' + file.pk + ',');
		});
	});
	$(document).on('click', '.pln-attachment-del', function(event){
		var container = $(this).closest('.pln-attachments');
		var field = $(container.data('field'));
		var attachment = $(this).closest('.pln-attachment');
		var pk = attachment.data('attachment');
		attachment.hide(300, function(){ attachment.remove(); });
		field.val(field.val().replace(',' + pk + ',', ','));
	});
	$(document).on('pln-dom-changed', function(event){ // Triggered by: poleno/js/ajax.js
		fileupload(event.target);
	});
	fileupload(document);
});

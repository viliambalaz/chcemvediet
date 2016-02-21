$(function(){
	function fileupload(base){
		var inputs = $(base).find('.pln-attachments input[type=file]');
		inputs.not('.hasFileupload').addClass('hasFileupload').each(function(){
			$(this).fileupload({
				dataType: 'json',
				singleFileUploads: false,
				limitMultiFileUploadSize: 15*1000*1000, // 15 MB
				formData: {'csrfmiddlewaretoken': $.cookie('csrftoken')},
			});
		});
	};
	function disable(container, disabled){
		var button = container.find('.pln-attachments-btn');
		var widget = button.find('input[type=file]');
		button.toggleClass('disabled', disabled);
		widget.prop('disabled', disabled);
	};
	function progress(container, percent, toggle){
		var progress = container.find('.pln-attachments-progress');
		var progressbar = progress.find('.progress-bar');
		progressbar.css({width: percent + '%'});
		progressbar.text(percent + '%');
		if (toggle == 'show') progress.show();
		if (toggle == 'hide') progress.hide();
		if (toggle == 'in') progress.slideDown(300);
		if (toggle == 'out') progress.slideUp(300);
	};
	function error(container, toggle){
		var alert = container.find('.pln-attachments-error .alert');
		if (toggle == 'show') alert.show();
		if (toggle == 'hide') alert.hide();
	};
	$(document).on('fileuploadstart', '.pln-attachments', function(event, data){
		var container = $(this);
		error(container, 'hide');
		disable(container, true);
		progress(container, 0, 'in');
	});
	$(document).on('fileuploadprogressall', '.pln-attachments', function(event, data){
		var container = $(this);
		var percent = (data.loaded / data.total * 100).toFixed();
		progress(container, percent)
	});
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
	$(document).on('fileuploadfail', '.pln-attachments', function(event, data){
		var container = $(this);
		progress(container, 0, 'hide');
		error(container, 'show');
	});
	$(document).on('fileuploadstop', '.pln-attachments', function(event, data){
		var container = $(this);
		disable(container, false);
		progress(container, 100, 'out');
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

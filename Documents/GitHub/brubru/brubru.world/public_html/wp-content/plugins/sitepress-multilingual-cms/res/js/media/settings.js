/*global jQuery, ajaxurl, addLoadEvent */
(function () {
	'use strict';

	addLoadEvent(
		function () {
			var form            = jQuery('#wpml_media_options_form');
			var form_action     = form.find('#wpml_media_options_action');
			var existingContent = form.find('.wpml-media-existing-content');
			var submitButton    = form.find(':submit');
			var primaryButton   = form.find('.button-primary');
      var shouldHandleMediaAutoSpinner = jQuery('#shouldhandlemediaautospinner');
      var shouldHandleMediaAutoCheckbox = jQuery('#shouldhandlemediaauto');
      var setupManuallyButton = jQuery('#show_hide-setup-manually');
      var setupManuallyContainer = jQuery('.setup-manually-container');

      var isFormVisible = false;

      form.addClass('collapsed');
      setupManuallyButton.addClass('collapsed');

      if (shouldHandleMediaAutoCheckbox.is(':checked')) {
        setupManuallyContainer.hide();
      }

      setupManuallyButton.on('click', function(e) {
        e.preventDefault();
        isFormVisible = !isFormVisible;

        if(isFormVisible) {
          form.removeClass('collapsed');
          setupManuallyButton.removeClass('collapsed');
        } else {
          form.addClass('collapsed');
          setupManuallyButton.addClass('collapsed');
        }
      });

      setTimeout(function() {
        var isShouldHandleMediaAutoChecked = parseInt(window.WPML_TM_SETTINGS.shouldHandleMediaAuto, 10) === 1;
        if (!isShouldHandleMediaAutoChecked) {
          shouldHandleMediaAutoCheckbox.prop('checked', false);
          update_should_handle_media_auto_box_style(false);
          show_all_media_controls();
          var wasNewMediaAutoSettingDisabled = localStorage.getItem('wasNewMediaAutoSettingDisabled') === '1';
          if (wasNewMediaAutoSettingDisabled) {
            set_unchecked_state_for_duplication_form();
          }
        } else {
          update_should_handle_media_auto_box_style(true);
        }
      }, 100);

			shouldHandleMediaAutoCheckbox.on('change', function() {
        var isShouldHandleMediaAutoChecked = shouldHandleMediaAutoCheckbox.is(':checked');
        show_should_handle_media_auto_spinner();
        wpml_media_save_should_handle_media_auto_setting( isShouldHandleMediaAutoChecked ? 1 : 0 );
        update_should_handle_media_auto_box_style(isShouldHandleMediaAutoChecked);

        if (isShouldHandleMediaAutoChecked && !form.hasClass('collapsed')) {
          form.addClass('collapsed');
          setupManuallyButton.addClass('collapsed');
          isFormVisible = false;
        }
      });

      var translateMediaLibraryTextsSpinner = jQuery('#translate_media_library_texts_spinner');
      var translateMediaLibraryTextsCheckbox = jQuery('#translate_media_library_texts');

      translateMediaLibraryTextsCheckbox.on('change', function() {
        var isChecked = translateMediaLibraryTextsCheckbox.is(':checked');
        show_translate_media_library_texts_spinner();
        wpml_media_set_content_defaults(
          function() {
            hide_translate_media_library_texts_spinner();
          },
          function() {
            hide_translate_media_library_texts_spinner();
            wpml_update_status('Set Content Defaults: Please try again (' + textStatus + ')');
          }
        );
      });

      var lastNewTranslateMediaIsChecked = false;
      var lastNewDuplicateMediaIsChecked = false;
      var lastTranslateMetadataIsChecked = false;
      function updateLastIsChecked() {
        lastNewTranslateMediaIsChecked = jQuery('input[name="' + 'content_default_always_translate_media' + '"]').is(':checked');
        lastNewDuplicateMediaIsChecked = jQuery('input[name="' + 'content_default_duplicate_featured' + '"]').is(':checked');
        lastTranslateMetadataIsChecked = jQuery('input[name="' + 'translate_media_library_texts' + '"]').is(':checked');
      }
      updateLastIsChecked();

			form.find(':checkbox').change(
				function () {
          var existingTranslateMedia = jQuery('#translate_media');
          var existingDuplicateMedia = jQuery('#duplicate_featured');
          var isExistingTranslateMediaChecked = existingTranslateMedia.is(':checked');
          var isExistingDuplicateMediaChecked = existingDuplicateMedia.is(':checked');

          var currNewTranslateMediaIsChecked = jQuery('input[name="' + 'content_default_always_translate_media' + '"]').is(':checked');
          var currNewDuplicateMediaIsChecked = jQuery('input[name="' + 'content_default_duplicate_featured' + '"]').is(':checked');

          var isChecked = (
            isExistingTranslateMediaChecked ||
            isExistingDuplicateMediaChecked ||
            lastNewTranslateMediaIsChecked !== currNewTranslateMediaIsChecked ||
            lastNewDuplicateMediaIsChecked !== currNewDuplicateMediaIsChecked
          );

					if (!isChecked) {
						primaryButton.addClass('disabled');
					} else {
						primaryButton.removeClass('disabled');
					}
				}
			);

			form.submit(
				function () {

					if (!submitButton.attr('disabled')) {
            jQuery(form).find('.content-progress').fadeIn();
            wpml_media_options_form_working();
            wpml_media_options_form_scan_prepare();
					}

					form_action.val(0);
					return false;
				}
			);

      function show_all_media_controls() {
        jQuery('#wpml-media-translation-should-handle-media-auto-notice').css('display', 'block');
      }

      function hide_all_media_controls() {
        jQuery('#wpml-media-translation-should-handle-media-auto-notice').css('display', 'none');
      }

      function update_should_handle_media_auto_box_style(isChecked) {
        var li = shouldHandleMediaAutoCheckbox.closest('li');
        var setupManuallyContainer = jQuery('.setup-manually-container');

        if (isChecked) {
          li.addClass('on').removeClass('off');
          setupManuallyContainer.hide();
        } else {
          li.removeClass('on').addClass('off');
          setupManuallyContainer.show();
        }
      }

      function show_should_handle_media_auto_spinner() {
        shouldHandleMediaAutoSpinner.css('display', 'grid').css('visibility', 'visible');
        shouldHandleMediaAutoCheckbox.parent().css('display', 'none');
      }

      function hide_should_handle_media_auto_spinner() {
        shouldHandleMediaAutoSpinner.css('display', 'none').css('visibility', 'hidden');
        shouldHandleMediaAutoCheckbox.parent().css('display', 'inline-flex');
      }

      function show_translate_media_library_texts_spinner() {
        translateMediaLibraryTextsSpinner.css('display', 'inline-block').css('visibility', 'visible');
        translateMediaLibraryTextsCheckbox.parent().css('display', 'none');
      }

      function hide_translate_media_library_texts_spinner() {
        translateMediaLibraryTextsSpinner.css('display', 'none').css('visibility', 'hidden');
        translateMediaLibraryTextsCheckbox.parent().css('display', 'inline-flex');
      }

			function wpml_update_status(message) {
				jQuery(form).find('.content-status').html(message);
				if (message.length > 0) {
					jQuery(form).find('.content-status').show();
				} else {
					jQuery(form).find('.content-status').fadeOut();
				}
			}

			function wpml_media_options_form_working() {
				wpml_update_status('');
				submitButton.prop('disabled', true);
				jQuery(form).find('.progress').fadeIn();
			}

			function wpml_media_options_form_finished(status) {
				submitButton.prop('disabled', false);
				jQuery(form).find('.progress').fadeOut();
				wpml_update_status(status);
				window.setTimeout(
					function () {
						wpml_update_status('');
					}, 1000
				);
			}

      function wpml_media_save_should_handle_media_auto_setting( isEnabled ) {
        jQuery.ajax(
          {
            url:      ajaxurl,
            type:     'POST',
            data:     {
              action: 'wpml_media_save_should_handle_media_auto_setting',
              nonce: wpml_media_settings_data.nonce_wpml_media_save_should_handle_media_auto_setting,
              isEnabled: isEnabled,
            },
            dataType: 'json',
            success:  function (ret) {
              hide_should_handle_media_auto_spinner();
              if (isEnabled) {
                hide_all_media_controls();
              } else {
                show_all_media_controls();
                set_unchecked_state_for_duplication_form();
                localStorage.setItem('wasNewMediaAutoSettingDisabled', '1');
              }
            },
            error:    function (jqXHR, textStatus) {
              hide_should_handle_media_auto_spinner();
              wpml_update_status('Save media setting: please try again (' + textStatus + ')');
            }
          }
        );

      }

      function set_unchecked_state_for_duplication_form() {
        jQuery('#translate_media').prop('checked', false);
        jQuery('#duplicate_featured').prop('checked', false);
        submitButton.addClass('disabled');
      }

			function wpml_media_options_form_scan_prepare() {
				jQuery.ajax(
					{
						url:      ajaxurl,
						type:     'POST',
						data:     {
							action: 'wpml_media_scan_prepare',
							nonce: wpml_media_settings_data.nonce_wpml_media_scan_prepare
						},
						dataType: 'json',
						success:  function (ret) {
							wpml_update_status(ret.message);
              wpml_media_translate_media();
						},
						error:    function (jqXHR, textStatus) {
							jQuery('#icl-migrate-progress').find('.message').html(textStatus);
						}

					}
				);

			}

			function wpml_media_translate_media() {
				if (jQuery('#translate_media', form).is(':checked')) {
					jQuery.ajax(
						{
							url:      ajaxurl,
							type:     'POST',
							data:     {
								action: 'wpml_media_translate_media',
								nonce: wpml_media_settings_data.nonce_wpml_media_translate_media
							},
							dataType: 'json',
							success:  function (ret) {
								wpml_update_status(ret.message);
								if (ret.left > 0) {
									wpml_media_translate_media();
								} else {
									// step 2
									wpml_media_duplicate_media();
								}
							},
							error:    function (jqXHR, textStatus) {
								wpml_update_status('Translate media: please try again (' + textStatus + ')');
							}

						}
					);
				} else {
					wpml_media_duplicate_media();
				}
			}

			function wpml_media_duplicate_media() {

        if (jQuery('#translate_media', form).is(':checked')) {
					jQuery.ajax(
						{
							url:      ajaxurl,
							type:     'POST',
							data:     {
								action: 'wpml_media_duplicate_media',
								nonce: wpml_media_settings_data.nonce_wpml_media_duplicate_media
							},
							dataType: 'json',
							success:  function (ret) {
								wpml_update_status(ret.message);
								if (ret.left > 0) {
									wpml_media_duplicate_media();
								} else {
									// step 3
									wpml_media_duplicate_featured_images();
								}
							},
							error:    function (jqXHR, textStatus) {
								wpml_update_status('Duplicate media: please try again (' + textStatus + ')');
							}

						}
					);
				} else {
					wpml_media_duplicate_featured_images();
				}
			}

			function wpml_media_duplicate_featured_images( left = null ) {
				if (jQuery('#duplicate_featured', form).is(':checked')) {
					jQuery.ajax(
						{
							url:      ajaxurl,
							type:     'POST',
							data:     {
								action: 'wpml_media_duplicate_featured_images',
								nonce: wpml_media_settings_data.nonce_wpml_media_duplicate_featured_images,
								featured_images_left: left
							},
							dataType: 'json',
							success:  function (ret) {
								wpml_update_status(ret.message);
								if (ret.left > 0) {
									wpml_media_duplicate_featured_images( ret.left );
								} else {
									wpml_media_mark_processed();
								}
							},
							error:    function (jqXHR, textStatus) {
								wpml_update_status('Duplicate featured images: Please try again (' + textStatus + ')');
							}

						}
					);
				} else {
					wpml_media_mark_processed();
				}
			}

			function wpml_media_mark_processed() {
				jQuery.ajax(
					{
						url:      ajaxurl,
						type:     'POST',
						data:     {
							action: 'wpml_media_mark_processed',
							nonce: wpml_media_settings_data.nonce_wpml_media_mark_processed
						},
						dataType: 'json',
						success:  function (ret) {
              wpml_media_set_content_prepare();
						},
						error:    function (jqXHR, textStatus) {
							wpml_update_status('Mark processed: Please try again (' + textStatus + ')');
						}

					}
				);

			}

			function wpml_media_set_content_prepare() {
				jQuery.ajax(
					{
						url:      ajaxurl,
						type:     'POST',
						data:     {
							action: 'wpml_media_set_content_prepare',
							nonce: wpml_media_settings_data.nonce_wpml_media_set_content_prepare
						},
						dataType: 'json',
						success:  function (ret) {
              jQuery(form).find('.content-status').css('display', 'inline');
							jQuery(form).find('.content-status').html('');
							wpml_media_set_content_defaults();
						},
						error:    function (jqXHR, textStatus) {
							wpml_update_status('Set Content Prepare: Please try again (' + textStatus + ')');
						}
					}
				);

			}

			function wpml_media_set_content_defaults(onSuccess, onError) {
        var onSuccess = onSuccess || function(ret) {
          jQuery(form).find('.content-status').html(ret.data.message);
          wpml_media_set_content_defaults_finished();
        };
        var onError = onError || function(jqXHR, textStatus) {
          wpml_update_status('Set Content Defaults: Please try again (' + textStatus + ')');
        };

				jQuery.ajax(
					{
						url:      ajaxurl,
						type:     'POST',
						data:     {
							action:                 'wpml_media_set_content_defaults',
							always_translate_media: jQuery('input[name=content_default_always_translate_media]', form).is(':checked'),
							duplicate_media:        jQuery('input[name=content_default_always_translate_media]', form).is(':checked'),
							duplicate_featured:     jQuery('input[name=content_default_duplicate_featured]', form).is(':checked'),
							translate_media_library_texts:     jQuery('input[name=translate_media_library_texts]', form).is(':checked'),
              				nonce: wpml_media_settings_data.nonce_wpml_media_set_content_defaults
						},
						dataType: 'json',
						success:  onSuccess,
						error: onError,
					}
				);

			}

			function wpml_media_set_content_defaults_finished() {
        updateLastIsChecked();
				submitButton.prop('disabled', false);
				jQuery(form).find('.content-progress').fadeOut();
				window.setTimeout(
					function () {
						jQuery(form).find('.content-status').fadeOut();
					}, 1000
				);
			}

		}
	);
}());

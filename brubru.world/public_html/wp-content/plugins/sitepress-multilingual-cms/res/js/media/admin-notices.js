/*global jQuery, ajaxurl, addLoadEvent */
(function () {
  'use strict';

  addLoadEvent(
    function () {
      var banner = jQuery('#admin_banner_about_automatic_media_detection');
      var notice = jQuery('#admin_banner_about_automatic_media_detection_after_30_days');
      var elementorNotice = jQuery('#admin_banner_for_elementor_on_mt_homepage');
      var bannerDismissButton = jQuery('#admin_banner_about_automatic_media_detection .dismiss-button');
      if ( bannerDismissButton.length ) {
        bannerDismissButton.on('click', function() {
          wpml_media_dismiss_should_handle_media_auto_banner();
        });
      }
      var noticeDismissButton = jQuery('#admin_banner_about_automatic_media_detection_after_30_days .dismiss-button');
      if ( noticeDismissButton.length ) {
        noticeDismissButton.on('click', function() {
          wpml_media_dismiss_should_handle_media_auto_notice();
        });
      }
      var elementorDismissButton = jQuery('#admin_banner_for_elementor_on_mt_homepage .dismiss-button');
      if ( elementorDismissButton.length ) {
        elementorDismissButton.on('click', function() {
          wpml_media_dismiss_elementor_notice();
        });
      }

      function wpml_media_dismiss_should_handle_media_auto_banner() {
        jQuery.ajax(
          {
            url:      ajaxurl,
            type:     'POST',
            data:     {
              action: 'wpml_media_dismiss_should_handle_media_auto_banner',
              nonce: wpml_media_admin_notices_data.nonce_wpml_media_dismiss_should_handle_media_auto_banner,
            },
            dataType: 'json',
            success:  function (ret) {
              banner.remove();
            },
          }
        );
      }

      function wpml_media_dismiss_should_handle_media_auto_notice() {
        jQuery.ajax(
          {
            url:      ajaxurl,
            type:     'POST',
            data:     {
              action: 'wpml_media_dismiss_should_handle_media_auto_notice',
              nonce: wpml_media_admin_notices_data.nonce_wpml_media_dismiss_should_handle_media_auto_notice,
            },
            dataType: 'json',
            success:  function (ret) {
              notice.remove();
            },
          }
        );
      }

      function wpml_media_dismiss_elementor_notice() {
        jQuery.ajax(
          {
            url:      ajaxurl,
            type:     'POST',
            data:     {
              action: 'wpml_media_dismiss_admin_notice_for_elementor_on_mt_homepage_notice',
              nonce: wpml_media_admin_notices_data.nonce_wpml_media_dismiss_admin_notice_for_elementor_on_mt_homepage_notice,
            },
            dataType: 'json',
            success:  function (ret) {
              elementorNotice.remove();
            },
          }
        );
      }
    }
  );
}());

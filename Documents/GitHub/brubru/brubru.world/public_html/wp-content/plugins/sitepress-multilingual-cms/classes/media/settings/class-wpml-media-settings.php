<?php

use WPML\LIB\WP\Nonce;
use WPML\Media\Option;

class WPML_Media_Settings {
	const ID = 'ml-content-setup-sec-media';

	private $wpdb;

	public function __construct( $wpdb ) {
		$this->wpdb = $wpdb;
	}

	public function add_hooks() {
		add_action( 'admin_enqueue_scripts', array( $this, 'enqueue_script' ) );
		add_action( 'icl_tm_menu_mcsetup', array( $this, 'render' ) );
		add_filter( 'wpml_mcsetup_navigation_links', array( $this, 'mcsetup_navigation_links' ) );
	}

	public function enqueue_script() {
		$handle = 'wpml-media-settings';

		wp_register_script(
			$handle,
			ICL_PLUGIN_URL . '/res/js/media/settings.js',
			[],
			ICL_SITEPRESS_SCRIPT_VERSION,
			true
		);

		wp_localize_script(
			$handle,
			'wpml_media_settings_data',
			[
				'nonce_wpml_media_save_should_handle_media_auto_setting' => wp_create_nonce( 'wpml_media_save_should_handle_media_auto_setting' ),
				'nonce_wpml_media_scan_prepare'         => wp_create_nonce( 'wpml_media_scan_prepare' ),
				'nonce_wpml_media_translate_media'      => wp_create_nonce( 'wpml_media_translate_media' ),
				'nonce_wpml_media_duplicate_featured_images' => wp_create_nonce( 'wpml_media_duplicate_featured_images' ),
				'nonce_wpml_media_set_content_prepare'  => wp_create_nonce( 'wpml_media_set_content_prepare' ),
				'nonce_wpml_media_set_content_defaults' => wp_create_nonce( 'wpml_media_set_content_defaults' ),
				'nonce_wpml_media_duplicate_media'      => wp_create_nonce( 'wpml_media_duplicate_media' ),
				'nonce_wpml_media_mark_processed'       => wp_create_nonce( 'wpml_media_mark_processed' ),
            ]
        );

		wp_enqueue_script( $handle );
	}

	public function render() {
		$is_st_disabled = ! defined( 'WPML_ST_VERSION' );
		?>
		<div class="wpml-section" id="<?php echo esc_attr( self::ID ); ?>">
			<div class="wpml-section-header">
				<h3><?php esc_html_e( 'Media Translation', 'sitepress' ); ?></h3>
				<a href="https://wpml.org/documentation/getting-started-guide/media-translation/?utm_source=plugin&utm_medium=gui&utm_campaign=wpmlmedia" target="_blank" class="wpml-external-link">
					<span><?php esc_html_e( 'Media Translation Documentation', 'sitepress' ); ?></span>
				</a>
			</div>

			<div class="wpml-section-content wpml-section-content-wide">
				<div class="wpml-settings-list" data-testid="wpml-media-translation-should-handle-media-auto">
					<div role="presentation">
						<ul class="settings-ul">
							<li aria-label="ShouldHandleMediaAuto" id="ShouldHandleMediaAuto" class="setting-item on">
								<span class="wpml-blue-badge wpml-green-badge solid">
									<?php echo esc_html_e( 'Recommended', 'sitepress' ); ?>
								</span>
								<div class="setting-item-title">
									<span class="setting-item-title-label">
										<?php echo esc_html_e( 'Automatically detect best options for translating image texts (alt, caption, title)', 'sitepress' ); ?>
										<span
											class="wpml-tooltip-button wpml-tooltip-button-inline js-wpml-hoverable-tooltip js-wpml-hoverable-tooltip-wide"
											data-content="<?php echo esc_attr__(
												// phpcs:ignore WordPress.WP.I18n.NonSingularStringLiteralText
												'This option ensures image texts (like alt, title, and caption) are translatable and displayed on the front-end. ' .
												'WPML duplicates media only when needed and only during translation, keeping your database clean and avoiding unnecessary entries.',
												'sitepress'
											);
											?>"
											data-link-text="<?php echo esc_attr__( 'Learn more about translating media with WPML', 'sitepress' ); ?>"
											data-link-url="https://wpml.org/documentation/getting-started-guide/media-translation/?utm_source=plugin&utm_medium=gui&utm_campaign=wpmlmedia"
											data-link-target="blank"
										>
											<button class="wpml-button base-btn edit-formality" data-testid="with-tooltip-null"></button>
										</span>
									</span>
									<span class="setting-item-title-sublabel">
										<?php echo esc_html_e( 'avoids unnecessary duplicate media fields and missing image translations', 'sitepress' ); ?>
									</span>
								</div>
								<label for="shouldhandlemediaauto" class="wpml-on-off-switch gray-dark">
									<input id="shouldhandlemediaauto" aria-labelledby="ShouldHandleMediaAuto" type="checkbox" <?php if ( Option::shouldHandleMediaAuto() ): ?>checked="checked" <?php endif; ?>/>
									<span aria-hidden="false" class="on"><?php echo esc_attr__( 'ON', 'sitepress' ); ?></span>
									<span aria-hidden="true" class="off"><?php echo esc_attr__( 'OFF', 'sitepress' ); ?></span>
									<span class="visually-hidden"></span>
								</label>
								<div id="shouldhandlemediaautospinner" style="display: none">
									<span class="media-spinner"></span>
								</div>
								<?php if ( $is_st_disabled ): ?><div class="disabled-control"></div><?php endif; ?>
							</li>
						</ul>

						<div id="wpml-media-translation-should-handle-media-auto-notice" class="warning notice-warning otgs-notice wpml-settings-list-notice" style="display: none">
							<p><?php echo esc_html_e( 'We recommend enabling automatic detection of image texts (alt, caption, title). This helps prevent duplicate media fields and missing translations.', 'sitepress' ); ?>
								<a href="https://wpml.org/documentation/getting-started-guide/media-translation/?utm_source=plugin&utm_medium=gui&utm_campaign=wpmlmedia" class="external-link" target="_blank"><?php echo esc_html_e( 'Learn more', 'sitepress' ); ?></a></p>
						</div>

						<div class="setup-manually-container">
							<h4>
								<button
									class="wpml-button base-btn text-button"
									id="show_hide-setup-manually"
									aria-controls="wpml_media_options_form"
								>
									<?php echo esc_html__( 'Setup manually', 'sitepress' ); ?>
								</button>
							</h4>
						</div>

						<?php if ( $is_st_disabled ): ?>
						<div class="warning notice-warning otgs-notice wpml-settings-list-notice">
							<p><?php echo esc_html_e( 'Please install and activate WPML’s String Translation add-on to use this setting.', 'sitepress' ); ?>
								<a href="<?php echo admin_url( 'plugins.php' ); ?>"><?php echo esc_html_e( 'Activate', 'sitepress' ); ?></a></p>
						</div>
						<?php endif; ?>
					</div>
				</div>

				<form aria-describedby="show_hide-setup-manually" id="wpml_media_options_form" style="margin-top: 32px;">
					<input type="hidden" id="wpml_media_options_action"/>
					<table class="wpml-settings-table wpml-media-existing-content wpml-list-with-tooltips">

						<?php
							$content_defaults = \WPML\Media\Option::getNewContentSettings();

							$always_translate_media_html_checked = $content_defaults['always_translate_media'] ? 'checked="checked"' : '';
							$duplicate_media_html_checked        = $content_defaults['duplicate_media'] ? 'checked="checked"' : '';
							$duplicate_featured_html_checked     = $content_defaults['duplicate_featured'] ? 'checked="checked"' : '';
						?>

						<tr>
							<th style="max-width: 230px;"></th>
							<th>
								<?php esc_html_e( 'Existing content', 'sitepress' ); ?>
							</th>
							<th>
								<?php esc_html_e( 'New content', 'sitepress' ); ?>
							</th>
						</tr>

						<tr class="header-separator">
							<td colspan="3"></td>
						</tr>

						<tr>
							<td style="max-width: 230px;">
								<?php esc_html_e( 'Duplicate texts (alt, caption, title) for all media to all languages', 'sitepress' ); ?>
								<span
									class="wpml-tooltip-button wpml-tooltip-button-inline external-link js-wpml-hoverable-tooltip"
									style="display: inline-block"
									data-content="<?php echo esc_attr__(
										'This applies to all types of media items (images, videos, PDFs, etc.) and not just images. WPML will only duplicate media texts (alt, caption, title) and not the media files.',
										'sitepress'
									);
									?>"
								>
									<button class="wpml-button base-btn tooltip" data-testid="with-tooltip-null"></button>
								</span>
							</td>
							<td style="text-align: center">
								<input type="checkbox" class="wpml-checkbox-native" id="translate_media" name="translate_media" value="1" checked="checked"/>
							</td>
							<td style="text-align: center">
								<input type="checkbox" class="wpml-checkbox-native" name="content_default_always_translate_media"
									   value="1" <?php echo $always_translate_media_html_checked; ?> />
							</td>
						</tr>

						<tr class="row-separator">
							<td colspan="3"></td>
						</tr>

						<tr>
							<td style="max-width: 230px;">
								<?php esc_html_e( 'Duplicate image texts (alt, caption, title) for all feature images to all languages', 'sitepress' ); ?>
								<span
									class="wpml-tooltip-button wpml-tooltip-button-inline external-link js-wpml-hoverable-tooltip"
									style="display: inline-block"
									data-content="<?php echo esc_attr__(
										'This applies to all types of media items (images, videos, PDFs, etc.) and not just images. WPML will only duplicate media texts (alt, caption, title) and not the media files.',
										'sitepress'
									);
									?>"
								>
									<button class="wpml-button base-btn tooltip" data-testid="with-tooltip-null"></button>
								</span>
							</td>
							<td style="text-align: center"><input type="checkbox" class="wpml-checkbox-native" id="duplicate_featured" name="duplicate_featured" value="1" checked="checked"/></td>
							<td style="text-align: center"><input type="checkbox" class="wpml-checkbox-native" name="content_default_duplicate_featured"
									   value="1" <?php echo $duplicate_featured_html_checked; ?> /></td>
						</tr>

						<tr class="row-separator">
							<td colspan="3"></td>
						</tr>

						<tr>
							<td colspan="2" style="text-align: left">
								<div style="margin-top: 25px; max-width: 300px; color: #2F7D92">
									<img class="content-progress" src="<?php echo ICL_PLUGIN_URL; ?>/res/img/ajax-loader.gif" width="16" height="16" alt="loading" style="display: none;"/>
									&nbsp;<span class="content-status"> </span>
								</div>
							</td>
							<td colspan="1" style="text-align: right">
								<span
									class="wpml-tooltip-button wpml-tooltip-button-inline js-wpml-hoverable-tooltip js-wpml-hoverable-tooltip-wide"
									data-content="<?php echo esc_attr__(
										// phpcs:ignore WordPress.WP.I18n.NonSingularStringLiteralText
										'This will duplicate media texts (alt, title, caption) to all languages using the options you selected above. ' .
										'Please stay on this page until the process completes - it may take a few minutes.',
										'sitepress'
									);
									?>"
								>
									<input class="button-primary wpml-button base-btn" name="set_defaults" type="submit" value="<?php esc_attr_e( 'Start the process', 'sitepress' ); ?>" style="margin-top: 30px"/>
								</span>
							</td>
						</tr>

					</table>

					<table class="wpml-media-new-content-settings wpml-list-with-tooltips wpml-settings-list">

						<tr>
							<td colspan="2">
								<h4 style="margin-bottom: 0"><?php esc_html_e( 'How to handle Media Library texts (alt, caption, title)', 'sitepress' ); ?></h4>
							</td>
						</tr>

						<tr>
							<td colspan="2">
								<ul class="wpml_media_options_media_library_texts settings-ul">
									<li aria-label="ShouldHandleMediaAuto" class="setting-item on" style="background-color: unset; border-color: transparent; padding: 0px">
										<label for="translate_media_library_texts" class="wpml-on-off-switch">
											<input id="translate_media_library_texts" name="translate_media_library_texts" type="checkbox"
												<?php
													if ( \WPML\Media\Option::getTranslateMediaLibraryTexts() ):
												?>checked="checked"<?php endif; ?>
											/>
											<span aria-hidden="false" class="on"><?php echo esc_attr__( 'ON', 'sitepress' ); ?></span>
											<span aria-hidden="true" class="off"><?php echo esc_attr__( 'OFF', 'sitepress' ); ?></span>
											<span class="visually-hidden"></span>
										</label>
										<div>
											<span id="translate_media_library_texts_spinner" class="spinner" style="display: none"></span>
										</div>
										<div class="setting-item-title">
											<span class="setting-item-title-label" style="font-weight: normal">
												<?php echo esc_html_e( 'Translate Media Library texts (alt, caption, title) when translating content', 'sitepress' ); ?>
												<span
													class="wpml-tooltip-button wpml-tooltip-button-inline js-wpml-hoverable-tooltip js-wpml-hoverable-tooltip-wide"
													data-content="<?php echo esc_attr__(
														// phpcs:ignore WordPress.WP.I18n.NonSingularStringLiteralText
														'Enable this option to translate image texts (alt, caption, title) for images connected to Media Library. ' .
														'Such images reuse the same texts across all posts and pages. This setting is required for page builders like Elementor and Divi.',
														'sitepress'
													);
													?>"
												>
													<button class="wpml-button base-btn edit-formality" data-testid="with-tooltip-null"></button>
												</span>
											</span>
										</div>
									</li>
								</ul>
							</td>
						</tr>

					</table>

					<div id="wpml_media_all_done" class="hidden updated">
						<p><?php esc_html_e( "You're all done. From now on, all new media files that you upload to content will receive a language. You can automatically duplicate them to translations from the post-edit screen.", 'sitepress' ); ?></p>
					</div>

				</form>
			</div>

		</div>
		<?php
	}

	public function mcsetup_navigation_links( array $mcsetup_sections ) {
		$mcsetup_sections[ self::ID ] = esc_html__( 'Media Translation', 'sitepress' );

		return $mcsetup_sections;
	}
}

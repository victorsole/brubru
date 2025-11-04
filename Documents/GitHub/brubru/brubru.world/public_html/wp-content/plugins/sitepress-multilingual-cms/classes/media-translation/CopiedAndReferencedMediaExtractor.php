<?php

namespace WPML\MediaTranslation;

use WPML\LIB\WP\Attachment;

class CopiedAndReferencedMediaExtractor {
	const COPIED_MEDIA_SHORTCODES = array( 'et_pb_image' );

	/**
	 * @var MediaImgParse
	 */
	private $media_parser;

	/**
	 * @var \SitePress $sitepress
	 */
	private $sitepress;

	/**
	 * @param MediaImgParse $media_parser
	 * @param \SitePress    $sitepress
	 */
	public function __construct(
		MediaImgParse $media_parser,
		\SitePress $sitepress
	) {
		$this->media_parser = $media_parser;
		$this->sitepress    = $sitepress;
	}

	/**
	 * @param array|\WP_Post $post
	 * @param bool           $get_attachment_ids_from_urls
	 */
	public function extract( $post, $get_attachment_ids_from_urls = true ) {
		if ( is_array( $post ) ) {
			$post = $post[0];
		}

		$pb_media = $this->get_page_builder_media( $post );

		list( $pb_copied_media, $pb_referenced_media ) = $this->part_page_builder_media( $pb_media );

		$copied_media_in_blocks = $this->media_parser->get_imgs_from_blocks( $post->post_content );
		$all_media_in_tags      = $this->media_parser->get_from_img_tags( $post->post_content, $get_attachment_ids_from_urls );

		$copied_media = array_merge(
			$copied_media_in_blocks,
			$pb_copied_media
		);

		$referenced_media = $pb_referenced_media;

		$referenced_media = $this->maybe_extract_post_thumbnail( $post, $referenced_media );
		// Note: check if we can utilize /woocommerce-multilingual/classes/media/Wrapper/Translatable.php for this.
		$referenced_media = $this->maybe_extract_woocommerce_gallery( $post, $referenced_media );
		$referenced_media = $this->maybe_extract_bricks_media( $post, $referenced_media );
		$referenced_media = $this->maybe_extract_siteorigin_media( $post, $referenced_media );
		foreach ( $referenced_media as &$item ) {
			$item['attachment_id'] = (int) $item['attachment_id'];
		}

		$classified_medias = array_merge(
			$copied_media,
			$referenced_media
		);

		$classified_media_srcs = array();
		foreach ( $classified_medias as $classified_media ) {
			$classified_media_srcs[] = Attachment::extractSrcFromAttributes( $classified_media );
		}
		$not_classified_media_in_tags = array();
		foreach ( $all_media_in_tags as $media_in_tag ) {
			if ( in_array( Attachment::extractSrcFromAttributes( $media_in_tag ), $classified_media_srcs, true ) ) {
				continue;
			}

			$not_classified_media_in_tags[] = $media_in_tag;
		}

		foreach ( $not_classified_media_in_tags as &$not_classified_media_in_tag ) {
			$not_classified_media_in_tag['attachment_id'] = null;

			if ( $get_attachment_ids_from_urls ) {
				$post_id = attachment_url_to_postid( Attachment::extractSrcFromAttributes( $not_classified_media_in_tag ) );
				if ( ! is_numeric( $post_id ) ) {
					continue;
				}
				$not_classified_media_in_tag['attachment_id'] = $post_id;
			}

			$copied_media[] = $not_classified_media_in_tag;
		}

		return array(
			$copied_media,
			$referenced_media,
		);
	}

	/**
	 * @param \WP_Post $post
	 *
	 * @return array
	 */
	private function get_page_builder_media( $post ) {
		do_action( 'wpml_pb_find_used_media_in_post', $post );
		$pb_media = apply_filters( 'wpml_pb_get_used_media_in_post', $post );
		if ( ! is_array( $pb_media ) ) {
			$pb_media = array();
		}

		$pb_media = array_map(
			function ( $media ) {
				return array(
					'attributes'    => array(
						'src'     => $media['url'],
						'alt'     => '',
						'caption' => '',
					),
					'attachment_id' => is_numeric( $media['id'] ) ? $media['id'] : attachment_url_to_postid( $media['url'] ),
					'shortcode'     => $media['shortcode'] ?? '',
				);
			},
			$pb_media
		);

		return $pb_media;
	}

	/**
	 * @param array $pb_media
	 *
	 * @return array
	 */
	private function part_page_builder_media( $pb_media ) {
		$copied     = array();
		$referenced = array();
		foreach ( $pb_media as $media ) {
			if ( empty( $media['attachment_id'] ) ) {
				continue;
			} elseif (
				array_key_exists( 'shortcode', $media ) &&
				in_array( $media['shortcode'], self::COPIED_MEDIA_SHORTCODES, true )
			) {
				$copied[] = $media;
				continue;
			}

			$referenced[] = $media;
		}

		return array( $copied, $referenced );
	}

	/**
	 * @param \WP_Post $post
	 * @param array    $referenced_media
	 *
	 * @return array
	 */
	private function maybe_extract_post_thumbnail( $post, $referenced_media ) {
		$featured_image = get_post_meta( $post->ID, '_thumbnail_id', true );
		if ( ! $featured_image ) {
			return $referenced_media;
		}

		$referenced_media = array_merge(
			$referenced_media,
			array(
				array(
					'attributes'    => array(
						'src'     => null,
						'alt'     => '',
						'caption' => '',
					),
					'attachment_id' => $featured_image,
				),
			)
		);

		return $referenced_media;
	}

	/**
	 * @param \WP_Post $post
	 * @param array    $referenced_media
	 *
	 * @return array
	 */
	private function maybe_extract_woocommerce_gallery( $post, $referenced_media ) {
		$woocommerce_gallery_images = get_post_meta( $post->ID, '_product_image_gallery', true );
		if ( ! $woocommerce_gallery_images ) {
			return $referenced_media;
		}

		$woocommerce_gallery_images = array_map( 'intval', explode( ',', $woocommerce_gallery_images ) );
		foreach ( $woocommerce_gallery_images as $woocommerce_gallery_image ) {
			$referenced_media = array_merge(
				$referenced_media,
				array(
					array(
						'attributes'    => array(
							'src'     => null,
							'alt'     => '',
							'caption' => '',
						),
						'attachment_id' => $woocommerce_gallery_image,
					),
				)
			);
		}

		return $referenced_media;
	}

	/**
	 * @param \WP_Post $post
	 * @param array    $referenced_media
	 *
	 * @return array
	 */
	private function maybe_extract_bricks_media( $post, $referenced_media ) {
		$all_meta = get_post_meta( $post->ID );
		$data     = [];

		foreach ( $all_meta as $key => $value ) {
			if ( strpos( $key, '_bricks_' ) === 0 ) {
				$item = maybe_unserialize( $value[0] );
				if ( is_array( $item ) ) {
					$data[] = $item;
				}
			}
		}
		if ( count( $data ) === 0 ) {
			return $referenced_media;
		}

		$iterator = function( $node ) use ( &$iterator, &$referenced_media ) {
			if ( ! is_array( $node ) ) {
				return;
			}

			if ( isset( $node['settings']['image'] ) ) {
				$image = $node['settings']['image'];

				$referenced_media[] = array(
					'attributes' => array(
						'src'     => $image['url'] ?? null,
						'alt'     => '',
						'caption' => '',
					),
					'attachment_id' => $image['id'] ?? null,
				);
			}

			if ( isset( $node['settings']['items']['images'] ) ) {
				$images = $node['settings']['items']['images'];

				if ( is_array( $images ) ) {
					foreach ( $images as $image ) {
						$referenced_media[] = array(
							'attributes' => array(
								'src' => $image['url'] ?? null,
								'alt' => '',
								'caption' => '',
							),
							'attachment_id' => $image['id'] ?? null,
						);
					}
				}
			}

			if ( isset( $node['settings']['_background']['image'] ) ) {
				$image = $node['settings']['_background']['image'];

				$referenced_media[] = array(
					'attributes' => array(
						'src'     => $image['url'] ?? null,
						'alt'     => '',
						'caption' => '',
					),
					'attachment_id' => $image['id'] ?? null,
				);
			}

			foreach ( $node as $value ) {
				if ( is_array( $value ) ) {
					$iterator( $value );
				}
			}
		};

		$iterator( $data );

		return $referenced_media;
	}

	/**
	 * @param \WP_Post $post
	 * @param array    $referenced_media
	 *
	 * @return array
	 */
	private function maybe_extract_siteorigin_media( $post, $referenced_media ) {
		$all_meta = get_post_meta( $post->ID );
		$data     = [];

		foreach ( $all_meta as $key => $value ) {
			if ( strpos( $key, 'panels_data' ) === 0 ) {
				$item = maybe_unserialize( $value[0] );
				if ( is_array( $item ) ) {
					$data[] = $item;
				}
			}
		}
		if ( count( $data ) === 0 ) {
			return $referenced_media;
		}

		$iterator = function( $node ) use ( &$iterator, &$referenced_media ) {
			if ( ! is_array( $node ) ) {
				return;
			}

			if ( isset( $node['option_name'] ) && $node['option_name'] === 'widget_sow-image' ) {
				$image = $node;

				$is_custom_alt_setup = isset( $node['alt'] ) && is_string( $node['alt'] ) && strlen( $node['alt'] ) > 0;
				if ( ! $is_custom_alt_setup ) {
					$referenced_media[] = array(
						'attributes' => array(
							'src'     => isset( $image['url'] ) && is_string( $image['url'] ) ? $image['url'] : null,
							'alt'     => '',
							'caption' => '',
						),
						'attachment_id' => isset( $image['image'] ) && is_numeric( $image['image'] ) ? $image['image'] : null,
					);
				}
			}

			if ( isset( $node['option_name'] ) && $node['option_name'] === 'widget_sow-slider' ) {
				$images = $node['frames'] ?? [];

				if ( is_array( $images ) ) {
					foreach ( $images as $image ) {
						if ( isset( $image['foreground_image'] ) && is_numeric( $image['foreground_image'] ) ) {
							$referenced_media[] = array(
								'attributes' => array(
									'src' => isset( $image['url'] ) && is_string( $image['url'] ) ? $image['url'] : null,
									'alt' => '',
									'caption' => '',
								),
								'attachment_id' => isset( $image['foreground_image'] ) && is_numeric( $image['foreground_image'] ) ? $image['foreground_image'] : null,
							);
						}
						if ( isset( $image['background_image'] ) && is_numeric( $image['background_image'] ) ) {
							$referenced_media[] = array(
								'attributes' => array(
									'src' => isset( $image['url'] ) && is_string( $image['url'] ) ? $image['url'] : null,
									'alt' => '',
									'caption' => '',
								),
								'attachment_id' => isset( $image['background_image'] ) && is_numeric( $image['background_image'] ) ? $image['background_image'] : null,
							);
						}
					}
				}
			}

			foreach ( $node as $value ) {
				if ( is_array( $value ) ) {
					$iterator( $value );
				}
			}
		};

		$iterator( $data );

		return $referenced_media;
	}
}

<?php

namespace WPML\CustomFieldTranslation;

use WPML\Convert\Ids;
use WPML\FP\Obj;
use WPML\Utils\TranslateNestedIds;
use WPML\Utils\XmlTranslatableIds;

abstract class TranslateIds {

	/** @var TranslationManagement $translationManagement */
	protected $translationManagement;
	/** @var WPML_WP_API $wpApi */
	protected $wpApi;
	/** @var TranslateNestedIds $translateNestedIds */
	protected $translateNestedIds;
	/** @var array $customFields */
	protected $customFields;

	/**
	 * @param TranslationManagement $translationManagement
	 * @param WPML_WP_API           $wpApi
	 * @param TranslateNestedIds    $translateNestedIds
	 */
	public function __construct( &$translationManagement, &$wpApi, $translateNestedIds ) {
		$this->translationManagement = &$translationManagement;
		$this->wpApi                 = &$wpApi;
		$this->translateNestedIds    = $translateNestedIds;

		$this->translationManagement->load_settings_if_required();
		$settings_key = $this->getTmSettingsKey();
		if ( isset( $this->translationManagement->settings[ $settings_key ] ) &&
				! empty( $this->translationManagement->settings[ $settings_key ] ) ) {

			$this->customFields = $this->translationManagement->settings[ $settings_key ];
		}
	}

	/**
	 * @return string
	 */
	abstract protected function getTmSettingsKey();

	/**
	 * @return bool
	 */
	public function hasCustomFields() {
		return (bool) $this->customFields;
	}

	/**
	 * @param mixed  $metadata  - Always null for post metadata.
	 * @param int    $object_id - Post ID for post metadata.
	 * @param string $meta_key  - metadata key.
	 * @param bool   $single    - Indicates if processing only a single $metadata value or array of values.
	 *
	 * @return mixed
	 */
	public function maybeTranslateIds( $metadata, $object_id, $meta_key, $single ) {
		if ( ! array_key_exists( $meta_key, $this->customFields ) ) {
			return $metadata;
		}
		if ( ! is_array( $this->customFields[ $meta_key ] ) ) {
			return $metadata;
		}

		$metadata_raw = $this->getRawValue( $metadata, $object_id, $meta_key, $single );
		if ( ! $metadata_raw ) {
			return $metadata;
		}

		if ( $single ) {
			$metadata_raw = array( $metadata_raw );
		}

		foreach ( $this->customFields[ $meta_key ] as $path_and_object_data ) {
			$type = Obj::propOr( XmlTranslatableIds::TYPE_POST_IDS, 'type', $path_and_object_data );
			$slug = Obj::propOr( Ids::ANY_POST, 'slug', $path_and_object_data );
			$path = explode( '>', Obj::propOr( '', 'path', $path_and_object_data ) );
			foreach ( $metadata_raw as &$metadata_raw_entry ) {
				$metadata_raw_entry = $this->translateNestedIds->convertByPath( $metadata_raw_entry, $path, $type, $slug );
			}
		}

		if ( $single && ! is_array( $metadata_raw[0] ) ) {
			$metadata_raw = $metadata_raw[0];
		}
		$metadata = $metadata_raw;

		return $metadata;
	}

	/**
	 * @param mixed  $metadata  - Always null for post metadata.
	 * @param int    $object_id - Post ID for post metadata.
	 * @param string $meta_key  - metadata key.
	 * @param bool   $single    - Indicates if processing only a single $metadata value or array of values.
	 *
	 * @return mixed
	 */
	abstract protected function getRawValue( $metadata, $object_id, $meta_key, $single );

}




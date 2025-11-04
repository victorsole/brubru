<?php

namespace WPML\WPSEO\YoastSEO\TranslationJob;

use WPML\FP\Obj;
use WPML\FP\Str;
use WPML\WPSEO\Shared\TranslationJob\BaseHooks;
use WPML\WPSEO\YoastSEO\Terms\Meta\Hooks as TermsMetaHooks;
use WPML\WPSEO\YoastSEO\Utils;

/**
 * @phpstan-import-type FieldArray from BaseHooks
 */
class Hooks extends BaseHooks {

	const OPTION_PREFIX = 'wpseo_';

	/**
	 * @inheritDoc
	 */
	protected function getFieldPrefix() {
		return 'field-_yoast_wpseo_';
	}

	/**
	 * @inheritDoc
	 */
	protected function getTopLevelGroup() {
		return [ self::OPTION_PREFIX => 'Yoast SEO' ];
	}

	/**
	 * @inheritDoc
	 */
	protected function getKeyPurposeMap() {
		return [
			'_yoast_wpseo_title'    => self::PURPOSE_SEO_TITLE,
			'_yoast_wpseo_metadesc' => self::PURPOSE_SEO_META_DESC,
		];
	}

	/**
	 * @param FieldArray   $field
	 * @param string|null  $fieldType
	 * @param object|mixed $job
	 *
	 * @return FieldArray
	 */
	protected function extraAdjustField( $field, $fieldType, $job ) {
		return $this->addPurposeToTermMeta( $field, $fieldType, $job );
	}

	/**
	 * @param FieldArray   $field
	 * @param string|null  $fieldType
	 * @param object|mixed $job
	 *
	 * @return FieldArray
	 */
	private function addPurposeToTermMeta( $field, $fieldType, $job ) {
		$jobType = Obj::prop( 'original_post_type', $job );

		if ( 'package_' . TermsMetaHooks::PACKAGE['kind_slug'] !== $jobType ) {
			return $field;
		}

		if ( Str::endsWith( Utils::KEY_META_TITLE, $fieldType ) ) {
			$field['purpose'] = self::PURPOSE_SEO_TITLE;
		} elseif ( Str::endsWith( Utils::KEY_META_DESC, $fieldType ) ) {
			$field['purpose'] = self::PURPOSE_SEO_META_DESC;
		}

		return $field;
	}
}

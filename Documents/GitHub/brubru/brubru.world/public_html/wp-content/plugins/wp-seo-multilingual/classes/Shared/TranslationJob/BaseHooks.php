<?php

namespace WPML\WPSEO\Shared\TranslationJob;

use WPML\FP\Str;
use WPML\FP\Obj;
use WPML\LIB\WP\Hooks;

use function WPML\FP\spreadArgs;

/**
 * @phpstan-type FieldArray array{
 *     field_type?: string,
 *     title?: string,
 *     group?: array<string,string>
 * }
 */
abstract class BaseHooks implements \IWPML_Frontend_Action, \IWPML_Backend_Action {

	const PURPOSE_SEO_TITLE     = 'seo_title';
	const PURPOSE_SEO_META_DESC = 'seo_meta_description';
	const PREFIX_JOB_FIELD_TERM = 't';

	public function add_hooks() {
		Hooks::onFilter( 'wpml_tm_adjust_translation_fields', 10, 2 )
			->then( spreadArgs( [ $this, 'adjustFields' ] ) );

		Hooks::onFilter( 'wpml_st_translation_job_admin_text_prefixes_to_groups' )
			->then( spreadArgs( [ $this, 'addAdminTextPrefix' ] ) );
	}

	/**
	 * @return string
	 */
	abstract protected function getFieldPrefix();

	/**
	 * @return array<string,string>
	 */
	abstract protected function getTopLevelGroup();

	/**
	 * @return array<string,string>
	 */
	abstract protected function getKeyPurposeMap();

	/**
	 * @param array<string,string> $prefixes
	 *
	 * @return array<string,string>
	 */
	public function addAdminTextPrefix( $prefixes ) {
		return array_merge( $prefixes, static::getTopLevelGroup() );
	}

	/**
	 * @param list<FieldArray> $fields
	 * @param object|mixed     $job
	 *
	 * @return list<FieldArray>
	 */
	public function adjustFields( $fields, $job ) {
		foreach ( $fields as &$field ) {
			$fieldType = Obj::prop( 'field_type', $field );
			$field     = $this->extraAdjustField( $field, $fieldType, $job );

			if ( preg_match( '/^' . self::PREFIX_JOB_FIELD_TERM . '?' . $this->getFieldPrefix() . '/', $fieldType ) ) {
				$field = $this->addTitleAndGroup( $field );
				$field = $this->addPurpose( $field );
			}
		}

		return $fields;
	}

	/**
	 * @param FieldArray   $field
	 * @param string|null  $fieldType
	 * @param object|mixed $job
	 *
	 * @return FieldArray
	 */
	protected function extraAdjustField( $field, $fieldType, $job ) {
		return $field;
	}

	/**
	 * @param FieldArray $field
	 *
	 * @return FieldArray
	 */
	private function addTitleAndGroup( $field ) {
		$title = (string) Obj::prop( 'title', $field );
		if ( $title && Str::startsWith( $this->getFieldPrefix(), $title ) ) {
			$field['title'] = apply_filters(
				'wpml_labelize_string',
				substr( $title, strlen( $this->getFieldPrefix() ) ),
				'TranslationJob'
			);
		}
		$field['group'] = $this->getTopLevelGroup();

		return $field;
	}

	/**
	 * @param FieldArray $field
	 *
	 * @return FieldArray
	 */
	private function addPurpose( $field ) {
		$fieldKey = preg_replace( '/^(' . self::PREFIX_JOB_FIELD_TERM . '?field-)(.*)(-\d+)$/', '$2', $field['field_type'] );

		$purpose = wpml_collect( $this->getKeyPurposeMap() )->get( $fieldKey );

		if ( $purpose ) {
			$field['purpose'] = $purpose;
		}

		return $field;
	}
}

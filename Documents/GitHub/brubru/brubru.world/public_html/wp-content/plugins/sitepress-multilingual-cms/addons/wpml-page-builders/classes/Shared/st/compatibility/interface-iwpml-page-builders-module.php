<?php

interface IWPML_Page_Builders_Module {

	/**
	 * @var string
	 */
	const FIELD_SEPARATOR = '>';

	/**
	 * @param string|int       $node_id
	 * @param mixed            $element
	 * @param WPML_PB_String[] $strings
	 *
	 * @return WPML_PB_String[]
	 */
	public function get( $node_id, $element, $strings );

	/**
	 * @param string|int     $node_id
	 * @param mixed          $element
	 * @param WPML_PB_String $pbString
	 *
	 * @return array|null
	 */
	public function update( $node_id, $element, WPML_PB_String $pbString );
}

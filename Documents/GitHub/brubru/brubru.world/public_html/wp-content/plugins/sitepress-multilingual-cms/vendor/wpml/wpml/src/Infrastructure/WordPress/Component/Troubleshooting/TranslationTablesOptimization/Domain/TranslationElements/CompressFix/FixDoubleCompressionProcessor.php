<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\CompressFix;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\ProcessorInterface;
use WPML\Translation\TranslationElements\FieldCompression;

/**
 * @implements ProcessorInterface<object{tid: int, fieldData: string, fieldDataTranslated: string}>
 */
class FixDoubleCompressionProcessor implements ProcessorInterface {

  /** @var \wpdb */
  private $wpdb;


  /**
   * @param \wpdb $wpdb
   */
  public function __construct( $wpdb ) {
    $this->wpdb = $wpdb;
  }


  /**
   * @param array<object{tid: int, fieldData: string, fieldDataTranslated: string}> $records
   *
   * @return int[]
   */
  public function process( array $records ): array {
    $processed  = [];
    $updateData = [];

    foreach ( $records as $record ) {
      // Check and fix double compression for field_data
      $fieldDataResult = FieldCompression::fixDoubleCompression( $record->fieldData );
      $fieldData       = $fieldDataResult['data'];

      // Check and fix double compression for field_data_translated
      $fieldDataTranslatedResult = FieldCompression::fixDoubleCompression( $record->fieldDataTranslated );
      $fieldDataTranslated       = $fieldDataTranslatedResult['data'];

      // Only update if double compression was detected in either field
      if ( $fieldDataResult['was_double_compressed'] || $fieldDataTranslatedResult['was_double_compressed'] ) {
        $updateData[] = [
          'tid'                   => $record->tid,
          'field_data'            => $fieldData,
          'field_data_translated' => $fieldDataTranslated,
        ];
      }

      $processed[] = $record->tid;
    }

    if ( ! empty( $updateData ) ) {
      $this->bulkUpdateTranslateTable( $updateData );
    }

    return $processed;
  }


  /**
   * @param array<array{tid: int|string, field_data: string|null, field_data_translated: string|null}> $data
   *
   * @return void
   */
  private function bulkUpdateTranslateTable( array $data ) {
    if ( empty( $data ) ) {
      return;
    }

    /** @var array<string> $fieldDataCases */
    $fieldDataCases = [];
    /** @var array<string> $fieldDataTranslatedCases */
    $fieldDataTranslatedCases = [];
    /** @var array<int> $tidValues */
    $tidValues = [];

    foreach ( $data as $record ) {
      $tid                        = (int) $record['tid'];
      $fieldDataCases[]           = $this->wpdb->prepare( 'WHEN tid = %d THEN %s', $tid, $record['field_data'] );
      $fieldDataTranslatedCases[] =
        $this->wpdb->prepare( 'WHEN tid = %d THEN %s', $tid, $record['field_data_translated'] );
      $tidValues[]                = $tid;
    }

    /**
     * @var string[] $fieldDataCases
     * @var string[] $fieldDataTranslatedCases
     */

    $tableName = $this->wpdb->prefix . 'icl_translate';
    $sql       = "UPDATE {$tableName} SET 
      field_data = CASE " . implode( ' ', $fieldDataCases ) . " END,
      field_data_translated = CASE " . implode( ' ', $fieldDataTranslatedCases ) . " END
      WHERE tid IN (" . implode( ',', $tidValues ) . ")";

    $this->wpdb->query( $sql );
  }


}

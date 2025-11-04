<?php

namespace WPML\Infrastructure\WordPress\Component\Troubleshooting\TranslationTablesOptimization\Domain\TranslationElements\Compress;

use WPML\Core\Component\Troubleshooting\TranslationTablesOptimization\Domain\MigrationDataService\ProcessorInterface;
use WPML\Translation\TranslationElements\FieldCompression;

/**
 * @implements ProcessorInterface<object{tid: int, fieldData: string, fieldDataTranslated: string}>
 */
class Processor implements ProcessorInterface {

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
      $compressedFieldData           = FieldCompression::compress( $record->fieldData );
      $compressedFieldDataTranslated = FieldCompression::compress( $record->fieldDataTranslated );

      $updateData[] = [
        'tid'                   => $record->tid,
        'field_data'            => $compressedFieldData,
        'field_data_translated' => $compressedFieldDataTranslated,
      ];

      $processed[] = $record->tid;
    }

    $this->bulkUpdateTranslateTable( $updateData );

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

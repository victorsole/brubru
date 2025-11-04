<?php

namespace WPML\Infrastructure\WordPress\Component\Translation\Application\Query;

use WPML\Core\Component\Translation\Application\Query\HasPostsUsingNativeEditorQueryInterface;
use WPML\Core\Port\Persistence\Exception\DatabaseErrorException;
use WPML\Core\Port\Persistence\QueryHandlerInterface;
use WPML\Core\Port\Persistence\QueryPrepareInterface;
use WPML\Core\SharedKernel\Component\Language\Application\Query\Dto\LanguageDto;
use WPML\Core\SharedKernel\Component\Language\Application\Query\LanguagesQueryInterface;
use WPML\Core\SharedKernel\Component\Translation\Domain\TranslationStatus;

class HasPostsUsingNativeEditorQuery implements HasPostsUsingNativeEditorQueryInterface {

  const POST_META_KEY_USE_NATIVE_EDITOR = '_wpml_post_translation_editor_native';

  /** @var QueryHandlerInterface<int, int|null> */
  private $queryHandler;

  /** @var QueryPrepareInterface */
  private $queryPrepare;

  /** @var LanguagesQueryInterface */
  private $languagesQuery;


  /**
   * @param QueryHandlerInterface<int, int|null> $queryHandler
   * @param QueryPrepareInterface                $queryPrepare
   * @param LanguagesQueryInterface              $languagesQuery
   */
  public function __construct(
    QueryHandlerInterface $queryHandler,
    QueryPrepareInterface $queryPrepare,
    LanguagesQueryInterface $languagesQuery
  ) {
    $this->queryHandler = $queryHandler;
    $this->queryPrepare = $queryPrepare;
    $this->languagesQuery = $languagesQuery;
  }


  /**
   * @param string[] $postTypes
   * @param string[] $postTypesUsingWpEditor
   *
   * @return bool
   * @throws DatabaseErrorException
   */
  public function get(
    array $postTypes,
    array $postTypesUsingWpEditor
  ) : bool {
    $dbPrefix = $this->queryPrepare->prefix();
    $sql = "
        SELECT
            wpml_p.ID
        FROM
            {$dbPrefix}posts wpml_p
        LEFT JOIN {$dbPrefix}postmeta wpml_pm ON
            wpml_p.ID = wpml_pm.post_id AND wpml_pm.meta_key = '" . self::POST_META_KEY_USE_NATIVE_EDITOR . "'
        INNER JOIN {$dbPrefix}icl_translations source_t ON
          wpml_p.ID = source_t.element_id AND source_t.element_type = CONCAT('post_', wpml_p.post_type) 
            AND source_t.source_language_code IS NULL
        {$this->buildLanguageCrossJoin()}
        LEFT JOIN {$dbPrefix}icl_translations target_t ON
          source_t.trid = target_t.trid AND target_t.language_code = secondary_langs.lang_code 
            AND target_t.source_language_code IS NOT NULL
        LEFT JOIN {$dbPrefix}icl_translation_status wpml_ts ON
          wpml_ts.translation_id = target_t.translation_id
        WHERE
          (
          wpml_ts.translation_id IS NULL OR wpml_ts.status = " . TranslationStatus::NOT_TRANSLATED . " 
            OR (wpml_ts.status = " . TranslationStatus::COMPLETE . " AND wpml_ts.needs_update = 1)
          )
          AND wpml_p.post_status = 'publish'
          {$this->getPostTypesIn( $postTypes )}
          {$this->getMetaValueCondition( $postTypesUsingWpEditor )}
        LIMIT 1";

    return (bool) $this->queryHandler->querySingle( $sql );
  }


  /**
   * @param string[] $postTypesUsingWpEditor
   *
   * @return string
   */
  private function getMetaValueCondition( array $postTypesUsingWpEditor ) : string {
    if ( $postTypesUsingWpEditor ) {
      return ' AND ( wpml_pm.meta_value = \'yes\' 
                  OR ( wpml_p.post_type IN 
                      (' . $this->queryPrepare->prepareIn( $postTypesUsingWpEditor ) . ') 
                       AND wpml_pm.meta_value IS NULL 
                     ) 
                  )';
    }

    return ' AND wpml_pm.meta_value = \'yes\'';
  }


  /**
   * @param string[] $postTypes
   *
   * @return string
   */
  private function getPostTypesIn( array $postTypes ) : string {
    return ! empty( $postTypes )
      ? ' AND wpml_p.post_type IN (' . $this->queryPrepare->prepareIn( $postTypes ) .') '
      : ' AND 1=0 ';
  }


  private function buildLanguageCrossJoin(): string {
    $languageSelect = array_map(
      function ( LanguageDto $language ) {
        return "SELECT '{$language->getCode()}' AS lang_code";
      },
      $this->languagesQuery->getSecondary()
    );
    $languageSelect    = implode( ' UNION ALL ', $languageSelect );

    return " CROSS JOIN (
				$languageSelect	
			) as secondary_langs ";
  }


}

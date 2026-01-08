<?php

namespace WPML\Core\Component\WordsToTranslate\Application\Service;

use WPML\Core\Component\WordsToTranslate\Domain\Item;
use WPML\Core\Component\WordsToTranslate\Domain\Job\Job;
use WPML\Core\Component\WordsToTranslate\Domain\Job\JobDTO;
use WPML\Core\Component\WordsToTranslate\Domain\Job\Provider as ProviderJob;
use WPML\Core\Component\WordsToTranslate\Domain\Job\Query\TranslationEngineQueryInterface;
use WPML\Core\Component\WordsToTranslate\Domain\Post\Provider as ProviderPost;
use WPML\Core\Component\WordsToTranslate\Domain\Provider;
use WPML\Core\Component\WordsToTranslate\Domain\StringBatch\Provider as ProviderStringBatch;
use WPML\Core\Component\WordsToTranslate\Domain\StringPackage\Provider as ProviderStringPackage;
use WPML\Core\Component\WordsToTranslate\Domain\Strings\Provider as ProviderString;
use WPML\PHP\Exception\InvalidArgumentException;
use WPML\PHP\Exception\RuntimeException;

class WordsToTranslateService {

  /** @var Provider */
  private $provider;

  /** @var ProviderJob */
  private $providerJob;

  /** @var TranslationEngineQueryInterface */
  private $translationEngineQuery;


  public function __construct(
    Provider $provider,
    ProviderJob $providerJob,
    TranslationEngineQueryInterface $translationEngineQuery
  ) {
    $this->provider = $provider;
    $this->providerJob = $providerJob;
    $this->translationEngineQuery = $translationEngineQuery;
  }


  /**
   * @param int $id
   * @param string $type
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item
   *
   * @throws InvalidArgumentException
   */
  public function getForIdAndType( $id, $type, $langs, $freshTranslation = false ) {
    switch ( $type ) {
      case ProviderPost::TYPE:
        return $this->getForPost( $id, $langs, $freshTranslation );
      case ProviderString::TYPE:
        return $this->getForString( $id, $langs, $freshTranslation );
      case ProviderStringPackage::TYPE:
        return $this->getForStringPackage( $id, $langs, $freshTranslation );
      default:
        throw new InvalidArgumentException( sprintf( 'Item type "%s" is not recognized.', $type ) );
    }
  }


  /**
   * @param int $idPost
   * @param string[] $langs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item
   *
   * @throws InvalidArgumentException
   */
  public function getForPost( $idPost, $langs, $freshTranslation = false ) {
    return $this->provider->getByIdAndTypeForLangs(
      $idPost,
      ProviderPost::TYPE,
      $langs,
      $freshTranslation
    );
  }


  /**
   * @param int $idString
   * @param string[] $targetLangs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item
   *
   * @throws InvalidArgumentException
   */
  public function getForString( $idString, $targetLangs, $freshTranslation = false ) {
    return $this->provider->getByIdAndTypeForLangs(
      $idString,
      ProviderString::TYPE,
      $targetLangs,
      $freshTranslation
    );
  }


  /**
   * @param int $idStringPackage
   * @param string[] $targetLangs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item
   *
   * @throws InvalidArgumentException
   */
  public function getForStringPackage( $idStringPackage, $targetLangs, $freshTranslation = false ) {
    return $this->provider->getByIdAndTypeForLangs(
      $idStringPackage,
      ProviderStringPackage::TYPE,
      $targetLangs,
      $freshTranslation
    );
  }


  /**
   * @param int $idBatch
   * @param string[] $targetLangs
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return Item
   *
   * @throws InvalidArgumentException
   */
  public function getForStringBatch( $idBatch, $targetLangs, $freshTranslation = false ) {
    return $this->provider->getByIdAndTypeForLangs(
      $idBatch,
      ProviderStringBatch::TYPE,
      $targetLangs,
      $freshTranslation
    );
  }


  /**
   * @param int $idJob
   * @param bool $freshTranslation When true, previous translations will be
   * ignored.
   *
   * @return JobDTO
   *
   * @throws InvalidArgumentException
   * @throws RuntimeException
   */
  public function getForJob( $idJob, $freshTranslation = false ) {
    return $this->providerJob->getById( $idJob, $freshTranslation );
  }


  /**
   * This will also load the item associated with the job.
   * It's only for debugging purposes, as it builds the full job object.
   *
   * WARNING: This method relays on the last completed job for the same trid as
   * as the requested $idJob - means the calculated words to translate will only
   * be correct if the $idJob is the last job for the trid.
   *
   * @param int $idJob
   *
   * @return Job
   *
   * @throws InvalidArgumentException
   * @throws RuntimeException
   */
  public function getForJobDebug( $idJob ) {
    return $this->providerJob->getWithItemById( $idJob );
  }


  /**
   * Returns the cost per word for the given language code.
   *
   * @param string $langCode
   * @param ?string $sourceLang
   *
   * @return int|false The cost per word in cents, or false if the language does not support automatic translation.
   *
   * @throws RuntimeException The translation engine for the language is not available.
   */
  public function getCostsPerWordForLang( string $langCode, $sourceLang = null ) {
    return $this->translationEngineQuery->getCostsPerWordForLang( $langCode, $sourceLang );
  }


}

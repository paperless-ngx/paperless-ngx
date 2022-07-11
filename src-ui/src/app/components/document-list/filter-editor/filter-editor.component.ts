import {
  Component,
  EventEmitter,
  Input,
  Output,
  OnInit,
  OnDestroy,
  ViewChild,
  ElementRef,
} from '@angular/core'
import { PaperlessTag } from 'src/app/data/paperless-tag'
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent'
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type'
import { Subject, Subscription } from 'rxjs'
import { debounceTime, distinctUntilChanged, filter } from 'rxjs/operators'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { filterRulesDiffer, FilterRule } from 'src/app/data/filter-rule'
import {
  FILTER_ADDED_AFTER,
  FILTER_ADDED_BEFORE,
  FILTER_ASN,
  FILTER_CORRESPONDENT,
  FILTER_CREATED_AFTER,
  FILTER_CREATED_BEFORE,
  FILTER_DOCUMENT_TYPE,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_FULLTEXT_QUERY,
  FILTER_HAS_ANY_TAG,
  FILTER_HAS_TAGS_ALL,
  FILTER_HAS_TAGS_ANY,
  FILTER_DOES_NOT_HAVE_TAG,
  FILTER_TITLE,
  FILTER_TITLE_CONTENT,
  FILTER_STORAGE_PATH,
  FILTER_ASN_ISNULL,
  FILTER_ASN_GT,
  FILTER_ASN_LT,
} from 'src/app/data/filter-rule-type'
import { FilterableDropdownSelectionModel } from '../../common/filterable-dropdown/filterable-dropdown.component'
import { ToggleableItemState } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import { DocumentService } from 'src/app/services/rest/document.service'
import { PaperlessDocument } from 'src/app/data/paperless-document'
import { PaperlessStoragePath } from 'src/app/data/paperless-storage-path'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'

const TEXT_FILTER_TARGET_TITLE = 'title'
const TEXT_FILTER_TARGET_TITLE_CONTENT = 'title-content'
const TEXT_FILTER_TARGET_ASN = 'asn'
const TEXT_FILTER_TARGET_FULLTEXT_QUERY = 'fulltext-query'
const TEXT_FILTER_TARGET_FULLTEXT_MORELIKE = 'fulltext-morelike'

const TEXT_FILTER_MODIFIER_EQUALS = 'equals'
const TEXT_FILTER_MODIFIER_NULL = 'is null'
const TEXT_FILTER_MODIFIER_NOTNULL = 'not null'
const TEXT_FILTER_MODIFIER_GT = 'greater'
const TEXT_FILTER_MODIFIER_LT = 'less'

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss'],
})
export class FilterEditorComponent implements OnInit, OnDestroy {
  generateFilterName() {
    if (this.filterRules.length == 1) {
      let rule = this.filterRules[0]
      switch (this.filterRules[0].rule_type) {
        case FILTER_CORRESPONDENT:
          if (rule.value) {
            return $localize`Correspondent: ${
              this.correspondents.find((c) => c.id == +rule.value)?.name
            }`
          } else {
            return $localize`Without correspondent`
          }

        case FILTER_DOCUMENT_TYPE:
          if (rule.value) {
            return $localize`Type: ${
              this.documentTypes.find((dt) => dt.id == +rule.value)?.name
            }`
          } else {
            return $localize`Without document type`
          }

        case FILTER_HAS_TAGS_ALL:
          return $localize`Tag: ${
            this.tags.find((t) => t.id == +rule.value)?.name
          }`

        case FILTER_HAS_ANY_TAG:
          if (rule.value == 'false') {
            return $localize`Without any tag`
          }

        case FILTER_TITLE:
          return $localize`Title: ${rule.value}`

        case FILTER_ASN:
          return $localize`ASN: ${rule.value}`
      }
    }

    return ''
  }

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    private documentService: DocumentService,
    private storagePathService: StoragePathService
  ) {}

  @ViewChild('textFilterInput')
  textFilterInput: ElementRef

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[] = []
  documentTypes: PaperlessDocumentType[] = []
  storagePaths: PaperlessStoragePath[] = []

  _textFilter = ''
  _moreLikeId: number
  _moreLikeDoc: PaperlessDocument

  get textFilterTargets() {
    let targets = [
      { id: TEXT_FILTER_TARGET_TITLE, name: $localize`Title` },
      {
        id: TEXT_FILTER_TARGET_TITLE_CONTENT,
        name: $localize`Title & content`,
      },
      { id: TEXT_FILTER_TARGET_ASN, name: $localize`ASN` },
      {
        id: TEXT_FILTER_TARGET_FULLTEXT_QUERY,
        name: $localize`Advanced search`,
      },
    ]
    if (this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE) {
      targets.push({
        id: TEXT_FILTER_TARGET_FULLTEXT_MORELIKE,
        name: $localize`More like`,
      })
    }
    return targets
  }

  textFilterTarget = TEXT_FILTER_TARGET_TITLE_CONTENT

  get textFilterTargetName() {
    return this.textFilterTargets.find((t) => t.id == this.textFilterTarget)
      ?.name
  }

  public textFilterModifier: string

  get textFilterModifiers() {
    return [
      {
        id: TEXT_FILTER_MODIFIER_EQUALS,
        label: $localize`equals`,
      },
      {
        id: TEXT_FILTER_MODIFIER_NULL,
        label: $localize`is empty`,
      },
      {
        id: TEXT_FILTER_MODIFIER_NOTNULL,
        label: $localize`is not empty`,
      },
      {
        id: TEXT_FILTER_MODIFIER_GT,
        label: $localize`greater than`,
      },
      {
        id: TEXT_FILTER_MODIFIER_LT,
        label: $localize`less than`,
      },
    ]
  }

  get textFilterModifierIsNull(): boolean {
    return [TEXT_FILTER_MODIFIER_NULL, TEXT_FILTER_MODIFIER_NOTNULL].includes(
      this.textFilterModifier
    )
  }

  tagSelectionModel = new FilterableDropdownSelectionModel()
  correspondentSelectionModel = new FilterableDropdownSelectionModel()
  documentTypeSelectionModel = new FilterableDropdownSelectionModel()
  storagePathSelectionModel = new FilterableDropdownSelectionModel()

  dateCreatedBefore: string
  dateCreatedAfter: string
  dateAddedBefore: string
  dateAddedAfter: string

  _unmodifiedFilterRules: FilterRule[] = []
  _filterRules: FilterRule[] = []

  @Input()
  set unmodifiedFilterRules(value: FilterRule[]) {
    this._unmodifiedFilterRules = value
    this.rulesModified = filterRulesDiffer(
      this._unmodifiedFilterRules,
      this._filterRules
    )
  }

  get unmodifiedFilterRules(): FilterRule[] {
    return this._unmodifiedFilterRules
  }

  @Input()
  set filterRules(value: FilterRule[]) {
    this._filterRules = value

    this.documentTypeSelectionModel.clear(false)
    this.storagePathSelectionModel.clear(false)
    this.tagSelectionModel.clear(false)
    this.correspondentSelectionModel.clear(false)
    this._textFilter = null
    this._moreLikeId = null
    this.dateAddedBefore = null
    this.dateAddedAfter = null
    this.dateCreatedBefore = null
    this.dateCreatedAfter = null
    this.textFilterModifier = TEXT_FILTER_MODIFIER_EQUALS

    value.forEach((rule) => {
      switch (rule.rule_type) {
        case FILTER_TITLE:
          this._textFilter = rule.value
          this.textFilterTarget = TEXT_FILTER_TARGET_TITLE
          break
        case FILTER_TITLE_CONTENT:
          this._textFilter = rule.value
          this.textFilterTarget = TEXT_FILTER_TARGET_TITLE_CONTENT
          break
        case FILTER_ASN:
          this._textFilter = rule.value
          this.textFilterTarget = TEXT_FILTER_TARGET_ASN
          break
        case FILTER_FULLTEXT_QUERY:
          this._textFilter = rule.value
          this.textFilterTarget = TEXT_FILTER_TARGET_FULLTEXT_QUERY
          break
        case FILTER_FULLTEXT_MORELIKE:
          this._moreLikeId = +rule.value
          this.textFilterTarget = TEXT_FILTER_TARGET_FULLTEXT_MORELIKE
          this.documentService.get(this._moreLikeId).subscribe((result) => {
            this._moreLikeDoc = result
            this._textFilter = result.title
          })
          break
        case FILTER_CREATED_AFTER:
          this.dateCreatedAfter = rule.value
          break
        case FILTER_CREATED_BEFORE:
          this.dateCreatedBefore = rule.value
          break
        case FILTER_ADDED_AFTER:
          this.dateAddedAfter = rule.value
          break
        case FILTER_ADDED_BEFORE:
          this.dateAddedBefore = rule.value
          break
        case FILTER_HAS_TAGS_ALL:
          this.tagSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_HAS_TAGS_ANY:
          this.tagSelectionModel.logicalOperator = 'or'
          this.tagSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_HAS_ANY_TAG:
          this.tagSelectionModel.set(null, ToggleableItemState.Selected, false)
          break
        case FILTER_DOES_NOT_HAVE_TAG:
          this.tagSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
            false
          )
          break
        case FILTER_CORRESPONDENT:
          this.correspondentSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_DOCUMENT_TYPE:
          this.documentTypeSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_STORAGE_PATH:
          this.storagePathSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_ASN_ISNULL:
          this.textFilterTarget = TEXT_FILTER_TARGET_ASN
          this.textFilterModifier =
            rule.value == 'true' || rule.value == '1'
              ? TEXT_FILTER_MODIFIER_NULL
              : TEXT_FILTER_MODIFIER_NOTNULL
          break
        case FILTER_ASN_GT:
          this.textFilterTarget = TEXT_FILTER_TARGET_ASN
          this.textFilterModifier = TEXT_FILTER_MODIFIER_GT
          this._textFilter = rule.value
          break
        case FILTER_ASN_LT:
          this.textFilterTarget = TEXT_FILTER_TARGET_ASN
          this.textFilterModifier = TEXT_FILTER_MODIFIER_LT
          this._textFilter = rule.value
          break
      }
    })
    this.rulesModified = filterRulesDiffer(
      this._unmodifiedFilterRules,
      this._filterRules
    )
  }

  get filterRules(): FilterRule[] {
    let filterRules: FilterRule[] = []
    if (
      this._textFilter &&
      this.textFilterTarget == TEXT_FILTER_TARGET_TITLE_CONTENT
    ) {
      filterRules.push({
        rule_type: FILTER_TITLE_CONTENT,
        value: this._textFilter,
      })
    }
    if (this._textFilter && this.textFilterTarget == TEXT_FILTER_TARGET_TITLE) {
      filterRules.push({ rule_type: FILTER_TITLE, value: this._textFilter })
    }
    if (this.textFilterTarget == TEXT_FILTER_TARGET_ASN) {
      if (
        this.textFilterModifier == TEXT_FILTER_MODIFIER_EQUALS &&
        this._textFilter
      ) {
        filterRules.push({ rule_type: FILTER_ASN, value: this._textFilter })
      } else if (this.textFilterModifierIsNull) {
        filterRules.push({
          rule_type: FILTER_ASN_ISNULL,
          value: (
            this.textFilterModifier == TEXT_FILTER_MODIFIER_NULL
          ).toString(),
        })
      } else if (
        [TEXT_FILTER_MODIFIER_GT, TEXT_FILTER_MODIFIER_LT].includes(
          this.textFilterModifier
        ) &&
        this._textFilter
      ) {
        filterRules.push({
          rule_type:
            this.textFilterModifier == TEXT_FILTER_MODIFIER_GT
              ? FILTER_ASN_GT
              : FILTER_ASN_LT,
          value: this._textFilter,
        })
      }
    }
    if (
      this._textFilter &&
      this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_QUERY
    ) {
      filterRules.push({
        rule_type: FILTER_FULLTEXT_QUERY,
        value: this._textFilter,
      })
    }
    if (
      this._moreLikeId &&
      this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE
    ) {
      filterRules.push({
        rule_type: FILTER_FULLTEXT_MORELIKE,
        value: this._moreLikeId?.toString(),
      })
    }
    if (this.tagSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_HAS_ANY_TAG, value: 'false' })
    } else {
      const tagFilterType =
        this.tagSelectionModel.logicalOperator == 'and'
          ? FILTER_HAS_TAGS_ALL
          : FILTER_HAS_TAGS_ANY
      this.tagSelectionModel
        .getSelectedItems()
        .filter((tag) => tag.id)
        .forEach((tag) => {
          filterRules.push({
            rule_type: tagFilterType,
            value: tag.id?.toString(),
          })
        })
      this.tagSelectionModel
        .getExcludedItems()
        .filter((tag) => tag.id)
        .forEach((tag) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_TAG,
            value: tag.id?.toString(),
          })
        })
    }
    this.correspondentSelectionModel
      .getSelectedItems()
      .forEach((correspondent) => {
        filterRules.push({
          rule_type: FILTER_CORRESPONDENT,
          value: correspondent.id?.toString(),
        })
      })
    this.documentTypeSelectionModel
      .getSelectedItems()
      .forEach((documentType) => {
        filterRules.push({
          rule_type: FILTER_DOCUMENT_TYPE,
          value: documentType.id?.toString(),
        })
      })
    this.storagePathSelectionModel.getSelectedItems().forEach((storagePath) => {
      filterRules.push({
        rule_type: FILTER_STORAGE_PATH,
        value: storagePath.id?.toString(),
      })
    })
    if (this.dateCreatedBefore) {
      filterRules.push({
        rule_type: FILTER_CREATED_BEFORE,
        value: this.dateCreatedBefore,
      })
    }
    if (this.dateCreatedAfter) {
      filterRules.push({
        rule_type: FILTER_CREATED_AFTER,
        value: this.dateCreatedAfter,
      })
    }
    if (this.dateAddedBefore) {
      filterRules.push({
        rule_type: FILTER_ADDED_BEFORE,
        value: this.dateAddedBefore,
      })
    }
    if (this.dateAddedAfter) {
      filterRules.push({
        rule_type: FILTER_ADDED_AFTER,
        value: this.dateAddedAfter,
      })
    }
    return filterRules
  }

  @Output()
  filterRulesChange = new EventEmitter<FilterRule[]>()

  rulesModified: boolean = false

  updateRules() {
    this.filterRulesChange.next(this.filterRules)
  }

  get textFilter() {
    return this.textFilterModifierIsNull ? '' : this._textFilter
  }

  set textFilter(value) {
    this.textFilterDebounce.next(value)
  }

  textFilterDebounce: Subject<string>
  subscription: Subscription

  ngOnInit() {
    this.tagService
      .listAll()
      .subscribe((result) => (this.tags = result.results))
    this.correspondentService
      .listAll()
      .subscribe((result) => (this.correspondents = result.results))
    this.documentTypeService
      .listAll()
      .subscribe((result) => (this.documentTypes = result.results))
    this.storagePathService
      .listAll()
      .subscribe((result) => (this.storagePaths = result.results))

    this.textFilterDebounce = new Subject<string>()

    this.subscription = this.textFilterDebounce
      .pipe(
        debounceTime(400),
        distinctUntilChanged(),
        filter((query) => !query.length || query.length > 2)
      )
      .subscribe((text) => this.updateTextFilter(text))

    if (this._textFilter) this.documentService.searchQuery = this._textFilter
  }

  ngOnDestroy() {
    this.textFilterDebounce.complete()
  }

  resetSelected() {
    this.textFilterTarget = TEXT_FILTER_TARGET_TITLE_CONTENT
    this.filterRules = this._unmodifiedFilterRules
    this.updateRules()
  }

  toggleTag(tagId: number) {
    this.tagSelectionModel.toggle(tagId)
  }

  toggleCorrespondent(correspondentId: number) {
    this.correspondentSelectionModel.toggle(correspondentId)
  }

  toggleDocumentType(documentTypeId: number) {
    this.documentTypeSelectionModel.toggle(documentTypeId)
  }

  toggleStoragePath(storagePathID: number) {
    this.storagePathSelectionModel.toggle(storagePathID)
  }

  onTagsDropdownOpen() {
    this.tagSelectionModel.apply()
  }

  onCorrespondentDropdownOpen() {
    this.correspondentSelectionModel.apply()
  }

  onDocumentTypeDropdownOpen() {
    this.documentTypeSelectionModel.apply()
  }

  onStoragePathDropdownOpen() {
    this.storagePathSelectionModel.apply()
  }

  updateTextFilter(text) {
    this._textFilter = text
    this.documentService.searchQuery = text
    this.updateRules()
  }

  textFilterEnter() {
    const filterString = (
      this.textFilterInput.nativeElement as HTMLInputElement
    ).value
    if (filterString.length) {
      this.updateTextFilter(filterString)
    }
  }

  changeTextFilterTarget(target) {
    if (
      this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE &&
      target != TEXT_FILTER_TARGET_FULLTEXT_MORELIKE
    ) {
      this._textFilter = ''
    }
    this.textFilterTarget = target
    this.textFilterInput.nativeElement.focus()
    this.updateRules()
  }

  textFilterModifierChange() {
    if (
      this.textFilterModifierIsNull ||
      ([
        TEXT_FILTER_MODIFIER_EQUALS,
        TEXT_FILTER_MODIFIER_GT,
        TEXT_FILTER_MODIFIER_LT,
      ].includes(this.textFilterModifier) &&
        this._textFilter)
    ) {
      this.updateRules()
    }
  }
}

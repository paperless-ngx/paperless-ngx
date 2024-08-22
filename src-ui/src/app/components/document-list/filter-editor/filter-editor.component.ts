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
import { Tag } from 'src/app/data/tag'
import { Correspondent } from 'src/app/data/correspondent'
import { DocumentType } from 'src/app/data/document-type'
import { Warehouse } from 'src/app/data/warehouse'
import { Subject, Subscription } from 'rxjs'
import { debounceTime, distinctUntilChanged, filter } from 'rxjs/operators'
import { DocumentTypeService } from 'src/app/services/rest/document-type.service'
import { TagService } from 'src/app/services/rest/tag.service'
import { CorrespondentService } from 'src/app/services/rest/correspondent.service'
import { FilterRule } from 'src/app/data/filter-rule'
import { filterRulesDiffer } from 'src/app/utils/filter-rules'
import {
  FILTER_ADDED_AFTER,
  FILTER_ADDED_BEFORE,
  FILTER_ASN,
  FILTER_HAS_CORRESPONDENT_ANY,
  FILTER_CREATED_AFTER,
  FILTER_CREATED_BEFORE,
  FILTER_HAS_DOCUMENT_TYPE_ANY,
  FILTER_FULLTEXT_MORELIKE,
  FILTER_FULLTEXT_QUERY,
  FILTER_HAS_ANY_TAG,
  FILTER_HAS_TAGS_ALL,
  FILTER_HAS_TAGS_ANY,
  FILTER_DOES_NOT_HAVE_TAG,
  FILTER_TITLE,
  FILTER_TITLE_CONTENT,
  FILTER_HAS_STORAGE_PATH_ANY,
  FILTER_HAS_WAREHOUSE_ANY,
  FILTER_ASN_ISNULL,
  FILTER_ASN_GT,
  FILTER_ASN_LT,
  FILTER_DOES_NOT_HAVE_CORRESPONDENT,
  FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
  FILTER_DOES_NOT_HAVE_STORAGE_PATH,
  FILTER_DOES_NOT_HAVE_WAREHOUSE,
  FILTER_DOCUMENT_TYPE,
  FILTER_CORRESPONDENT,
  FILTER_STORAGE_PATH,
  FILTER_WAREHOUSE,
  FILTER_OWNER,
  FILTER_OWNER_DOES_NOT_INCLUDE,
  FILTER_OWNER_ISNULL,
  FILTER_OWNER_ANY,
  FILTER_CUSTOM_FIELDS,
  FILTER_SHARED_BY_USER,
  FILTER_CUSTOM_SHELF,
  FILTER_HAS_CUSTOM_SHELF_ANY,
  FILTER_BOX,
  FILTER_HAS_BOX_ANY,
  FILTER_DOES_NOT_HAVE_CUSTOM_SHELF,
  FILTER_DOES_NOT_HAVE_BOX,
} from 'src/app/data/filter-rule-type'
import {
  FilterableDropdownSelectionModel,
  Intersection,
  LogicalOperator,
} from '../../common/filterable-dropdown/filterable-dropdown.component'
import { ToggleableItemState } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component'
import {
  DocumentService,
  SelectionData,
  SelectionDataItem,
} from 'src/app/services/rest/document.service'
import { Document } from 'src/app/data/document'
import { StoragePath } from 'src/app/data/storage-path'
import { StoragePathService } from 'src/app/services/rest/storage-path.service'
import { RelativeDate } from '../../common/date-dropdown/date-dropdown.component'
import {
  OwnerFilterType,
  PermissionsSelectionModel,
} from '../../common/permissions-filter-dropdown/permissions-filter-dropdown.component'
import {
  PermissionAction,
  PermissionType,
  PermissionsService,
} from 'src/app/services/permissions.service'
import { ComponentWithPermissions } from '../../with-permissions/with-permissions.component'
import { WarehouseService } from 'src/app/services/rest/warehouse.service'

const TEXT_FILTER_TARGET_TITLE = 'title'
const TEXT_FILTER_TARGET_TITLE_CONTENT = 'title-content'
const TEXT_FILTER_TARGET_ASN = 'asn'
const TEXT_FILTER_TARGET_FULLTEXT_QUERY = 'fulltext-query'
const TEXT_FILTER_TARGET_FULLTEXT_MORELIKE = 'fulltext-morelike'
const TEXT_FILTER_TARGET_CUSTOM_FIELDS = 'custom-fields'

const TEXT_FILTER_MODIFIER_EQUALS = 'equals'
const TEXT_FILTER_MODIFIER_NULL = 'is null'
const TEXT_FILTER_MODIFIER_NOTNULL = 'not null'
const TEXT_FILTER_MODIFIER_GT = 'greater'
const TEXT_FILTER_MODIFIER_LT = 'less'

const RELATIVE_DATE_QUERY_REGEXP_CREATED = /created:\[([^\]]+)\]/g
const RELATIVE_DATE_QUERY_REGEXP_ADDED = /added:\[([^\]]+)\]/g
const RELATIVE_DATE_QUERYSTRINGS = [
  {
    relativeDate: RelativeDate.LAST_7_DAYS,
    dateQuery: '-1 week to now',
  },
  {
    relativeDate: RelativeDate.LAST_MONTH,
    dateQuery: '-1 month to now',
  },
  {
    relativeDate: RelativeDate.LAST_3_MONTHS,
    dateQuery: '-3 month to now',
  },
  {
    relativeDate: RelativeDate.LAST_YEAR,
    dateQuery: '-1 year to now',
  },
]

const DEFAULT_TEXT_FILTER_TARGET_OPTIONS = [
  { id: TEXT_FILTER_TARGET_TITLE, name: $localize`Title` },
  {
    id: TEXT_FILTER_TARGET_TITLE_CONTENT,
    name: $localize`Title & content`,
  },
  { id: TEXT_FILTER_TARGET_ASN, name: $localize`ASN` },
  {
    id: TEXT_FILTER_TARGET_CUSTOM_FIELDS,
    name: $localize`Custom fields`,
  },
  {
    id: TEXT_FILTER_TARGET_FULLTEXT_QUERY,
    name: $localize`Advanced search`,
  },
]

const TEXT_FILTER_TARGET_MORELIKE_OPTION = {
  id: TEXT_FILTER_TARGET_FULLTEXT_MORELIKE,
  name: $localize`More like`,
}

const DEFAULT_TEXT_FILTER_MODIFIER_OPTIONS = [
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

@Component({
  selector: 'pngx-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss'],
})
export class FilterEditorComponent
  extends ComponentWithPermissions
  implements OnInit, OnDestroy {
  generateFilterName() {
    if (this.filterRules.length == 1) {
      let rule = this.filterRules[0]
      switch (rule.rule_type) {
        case FILTER_CORRESPONDENT:
        case FILTER_HAS_CORRESPONDENT_ANY:
          if (rule.value) {
            return $localize`Correspondent: ${this.correspondents.find(
              (c) => c.id == +rule.value
            )?.name}`
          } else {
            return $localize`Without correspondent`
          }

        case FILTER_DOCUMENT_TYPE:
        case FILTER_HAS_DOCUMENT_TYPE_ANY:
          if (rule.value) {
            return $localize`Document type: ${this.documentTypes.find(
              (dt) => dt.id == +rule.value
            )?.name}`
          } else {
            return $localize`Without document type`
          }

        case FILTER_WAREHOUSE:
        case FILTER_HAS_WAREHOUSE_ANY:
          if (rule.value) {
            return $localize`Warehouse: ${this.warehouses.find(
              (w) => w.id == +rule.value
            )?.name}`
          } else {
            return $localize`Without warehouse`
          }
        case FILTER_CUSTOM_SHELF:
        case FILTER_HAS_CUSTOM_SHELF_ANY:
          if (rule.value) {
            return $localize`Shelf: ${this.shelfs.find(
              (w) => w.id == +rule.value
            )?.name}`
          } else {
            return $localize`Without shelf`
          }
        case FILTER_BOX:
        case FILTER_HAS_BOX_ANY:
          if (rule.value) {
            return $localize`Boxcase: ${this.boxcases.find(
              (w) => w.id == +rule.value
            )?.name}`
          } else {
            return $localize`Without boxcase`
          }

        case FILTER_STORAGE_PATH:
        case FILTER_HAS_STORAGE_PATH_ANY:
          if (rule.value) {
            return $localize`Storage path: ${this.storagePaths.find(
              (sp) => sp.id == +rule.value
            )?.name}`
          } else {
            return $localize`Without storage path`
          }

        case FILTER_HAS_TAGS_ALL:
          return $localize`Tag: ${this.tags.find((t) => t.id == +rule.value)
            ?.name}`

        case FILTER_HAS_ANY_TAG:
          if (rule.value == 'false') {
            return $localize`Without any tag`
          }

        case FILTER_TITLE:
          return $localize`Title: ${rule.value}`

        case FILTER_ASN:
          return $localize`ASN: ${rule.value}`

        case FILTER_OWNER:
          return $localize`Owner: ${rule.value}`

        case FILTER_OWNER_DOES_NOT_INCLUDE:
          return $localize`Owner not in: ${rule.value}`

        case FILTER_OWNER_ISNULL:
          return $localize`Without an owner`
      }
    }

    return ''
  }

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private warehouseService: WarehouseService,
    private correspondentService: CorrespondentService,
    private documentService: DocumentService,
    private storagePathService: StoragePathService,
    public permissionsService: PermissionsService
  ) {
    super()
  }

  @ViewChild('textFilterInput')
  textFilterInput: ElementRef

  tags: Tag[] = []
  correspondents: Correspondent[] = []
  documentTypes: DocumentType[] = []
  storagePaths: StoragePath[] = []
  warehouses: Warehouse[] = []
  shelfs: Warehouse[] = []
  boxcases: Warehouse[] = []

  tagDocumentCounts: SelectionDataItem[]
  correspondentDocumentCounts: SelectionDataItem[]
  documentTypeDocumentCounts: SelectionDataItem[]
  storagePathDocumentCounts: SelectionDataItem[]
  warehouseDocumentCounts: SelectionDataItem[]
  shelfDocumentCounts: SelectionDataItem[]
  boxcaseDocumentCounts: SelectionDataItem[]

  _textFilter = ''
  _moreLikeId: number
  _moreLikeDoc: Document

  get textFilterTargets() {
    if (this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE) {
      return DEFAULT_TEXT_FILTER_TARGET_OPTIONS.concat([
        TEXT_FILTER_TARGET_MORELIKE_OPTION,
      ])
    }
    return DEFAULT_TEXT_FILTER_TARGET_OPTIONS
  }

  textFilterTarget = TEXT_FILTER_TARGET_TITLE_CONTENT

  get textFilterTargetName() {
    return this.textFilterTargets.find((t) => t.id == this.textFilterTarget)
      ?.name
  }

  public textFilterModifier: string

  get textFilterModifiers() {
    return DEFAULT_TEXT_FILTER_MODIFIER_OPTIONS
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
  warehouseSelectionModel = new FilterableDropdownSelectionModel()
  shelfSelectionModel = new FilterableDropdownSelectionModel()
  boxcaseSelectionModel = new FilterableDropdownSelectionModel()


  dateCreatedBefore: string
  dateCreatedAfter: string
  dateAddedBefore: string
  dateAddedAfter: string
  dateCreatedRelativeDate: RelativeDate
  dateAddedRelativeDate: RelativeDate

  permissionsSelectionModel = new PermissionsSelectionModel()

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
    this.warehouseSelectionModel.clear(false)
    this.shelfSelectionModel.clear(false)
    this.boxcaseSelectionModel.clear(false)
    this.tagSelectionModel.clear(false)
    this.correspondentSelectionModel.clear(false)
    this._textFilter = null
    this._moreLikeId = null
    this.dateAddedBefore = null
    this.dateAddedAfter = null
    this.dateCreatedBefore = null
    this.dateCreatedAfter = null
    this.dateCreatedRelativeDate = null
    this.dateAddedRelativeDate = null
    this.textFilterModifier = TEXT_FILTER_MODIFIER_EQUALS
    this.permissionsSelectionModel.clear()

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
        case FILTER_CUSTOM_FIELDS:
          this._textFilter = rule.value
          this.textFilterTarget = TEXT_FILTER_TARGET_CUSTOM_FIELDS
          break
        case FILTER_FULLTEXT_QUERY:
          let allQueryArgs = rule.value.split(',')
          let textQueryArgs = []
          allQueryArgs.forEach((arg) => {
            if (arg.match(RELATIVE_DATE_QUERY_REGEXP_CREATED)) {
              ;[...arg.matchAll(RELATIVE_DATE_QUERY_REGEXP_CREATED)].forEach(
                (match) => {
                  if (match[1]?.length) {
                    this.dateCreatedRelativeDate =
                      RELATIVE_DATE_QUERYSTRINGS.find(
                        (qS) => qS.dateQuery == match[1]
                      )?.relativeDate ?? null
                  }
                }
              )
              if (this.dateCreatedRelativeDate === null) textQueryArgs.push(arg) // relative query not in the quick list
            } else if (arg.match(RELATIVE_DATE_QUERY_REGEXP_ADDED)) {
              ;[...arg.matchAll(RELATIVE_DATE_QUERY_REGEXP_ADDED)].forEach(
                (match) => {
                  if (match[1]?.length) {
                    this.dateAddedRelativeDate =
                      RELATIVE_DATE_QUERYSTRINGS.find(
                        (qS) => qS.dateQuery == match[1]
                      )?.relativeDate ?? null
                  }
                }
              )
              if (this.dateAddedRelativeDate === null) textQueryArgs.push(arg) // relative query not in the quick list
            } else {
              textQueryArgs.push(arg)
            }
          })
          if (textQueryArgs.length) {
            this._textFilter = textQueryArgs.join(',')
            this.textFilterTarget = TEXT_FILTER_TARGET_FULLTEXT_QUERY
          }
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
          this.tagSelectionModel.logicalOperator = LogicalOperator.And
          this.tagSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_HAS_TAGS_ANY:
          this.tagSelectionModel.logicalOperator = LogicalOperator.Or
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
        case FILTER_HAS_CORRESPONDENT_ANY:
          this.correspondentSelectionModel.logicalOperator = LogicalOperator.Or
          this.correspondentSelectionModel.intersection = Intersection.Include
          this.correspondentSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_DOES_NOT_HAVE_CORRESPONDENT:
          this.correspondentSelectionModel.intersection = Intersection.Exclude
          this.correspondentSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
            false
          )
          break
        case FILTER_DOCUMENT_TYPE:
        case FILTER_HAS_DOCUMENT_TYPE_ANY:
          this.documentTypeSelectionModel.logicalOperator = LogicalOperator.Or
          this.documentTypeSelectionModel.intersection = Intersection.Include
          this.documentTypeSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE:
          this.documentTypeSelectionModel.intersection = Intersection.Exclude
          this.documentTypeSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
            false
          )
          break
        case FILTER_WAREHOUSE:
        case FILTER_HAS_WAREHOUSE_ANY:
          this.warehouseSelectionModel.logicalOperator = LogicalOperator.Or
          this.warehouseSelectionModel.intersection = Intersection.Include
          this.warehouseSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_CUSTOM_SHELF:
        case FILTER_HAS_CUSTOM_SHELF_ANY:
          this.shelfSelectionModel.logicalOperator = LogicalOperator.Or
          this.shelfSelectionModel.intersection = Intersection.Include
          this.shelfSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_BOX:
        case FILTER_HAS_BOX_ANY:
          this.boxcaseSelectionModel.logicalOperator = LogicalOperator.Or
          this.boxcaseSelectionModel.intersection = Intersection.Include
          this.boxcaseSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_DOES_NOT_HAVE_WAREHOUSE:
          this.warehouseSelectionModel.intersection = Intersection.Exclude
          this.warehouseSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
            false
          )
          break
        case FILTER_DOES_NOT_HAVE_CUSTOM_SHELF:
          this.shelfSelectionModel.intersection = Intersection.Exclude
          this.shelfSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
            false
          )
          break
        case FILTER_DOES_NOT_HAVE_BOX:
          this.boxcaseSelectionModel.intersection = Intersection.Exclude
          this.boxcaseSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
            false
          )
          break
        case FILTER_STORAGE_PATH:
        case FILTER_HAS_STORAGE_PATH_ANY:
          this.storagePathSelectionModel.logicalOperator = LogicalOperator.Or
          this.storagePathSelectionModel.intersection = Intersection.Include
          this.storagePathSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Selected,
            false
          )
          break
        case FILTER_DOES_NOT_HAVE_STORAGE_PATH:
          this.storagePathSelectionModel.intersection = Intersection.Exclude
          this.storagePathSelectionModel.set(
            rule.value ? +rule.value : null,
            ToggleableItemState.Excluded,
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
        case FILTER_OWNER:
          this.permissionsSelectionModel.ownerFilter = OwnerFilterType.SELF
          this.permissionsSelectionModel.hideUnowned = false
          if (rule.value)
            this.permissionsSelectionModel.userID = parseInt(rule.value, 10)
          break
        case FILTER_OWNER_ANY:
          this.permissionsSelectionModel.ownerFilter = OwnerFilterType.OTHERS
          if (rule.value)
            this.permissionsSelectionModel.includeUsers.push(
              parseInt(rule.value, 10)
            )
          break
        case FILTER_OWNER_DOES_NOT_INCLUDE:
          this.permissionsSelectionModel.ownerFilter = OwnerFilterType.NOT_SELF
          if (rule.value)
            this.permissionsSelectionModel.excludeUsers.push(
              parseInt(rule.value, 10)
            )
          break
        case FILTER_SHARED_BY_USER:
          this.permissionsSelectionModel.ownerFilter =
            OwnerFilterType.SHARED_BY_ME
          if (rule.value)
            this.permissionsSelectionModel.userID = parseInt(rule.value, 10)
          break
        case FILTER_OWNER_ISNULL:
          if (rule.value === 'true' || rule.value === '1') {
            this.permissionsSelectionModel.hideUnowned = false
            this.permissionsSelectionModel.ownerFilter = OwnerFilterType.UNOWNED
          } else {
            this.permissionsSelectionModel.hideUnowned =
              rule.value === 'false' || rule.value === '0'
            break
          }
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
      this.textFilterTarget == TEXT_FILTER_TARGET_CUSTOM_FIELDS
    ) {
      filterRules.push({
        rule_type: FILTER_CUSTOM_FIELDS,
        value: this._textFilter,
      })
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
        value: this._moreLikeId.toString(),
      })
    }
    if (this.tagSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_HAS_ANY_TAG, value: 'false' })
    } else {
      const tagFilterType =
        this.tagSelectionModel.logicalOperator == LogicalOperator.And
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
    if (this.correspondentSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_CORRESPONDENT, value: null })
    } else {
      this.correspondentSelectionModel
        .getSelectedItems()
        .forEach((correspondent) => {
          filterRules.push({
            rule_type: FILTER_HAS_CORRESPONDENT_ANY,
            value: correspondent.id?.toString(),
          })
        })
      this.correspondentSelectionModel
        .getExcludedItems()
        .forEach((correspondent) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_CORRESPONDENT,
            value: correspondent.id?.toString(),
          })
        })
    }
    if (this.documentTypeSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_DOCUMENT_TYPE, value: null })
    } else {
      this.documentTypeSelectionModel
        .getSelectedItems()
        .forEach((documentType) => {
          filterRules.push({
            rule_type: FILTER_HAS_DOCUMENT_TYPE_ANY,
            value: documentType.id?.toString(),
          })
        })
      this.documentTypeSelectionModel
        .getExcludedItems()
        .forEach((documentType) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_DOCUMENT_TYPE,
            value: documentType.id?.toString(),
          })
        })
    }
    if (this.warehouseSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_WAREHOUSE, value: null })
    } else {
      this.warehouseSelectionModel
        .getSelectedItems()
        .forEach((warehouse) => {
          filterRules.push({
            rule_type: FILTER_HAS_WAREHOUSE_ANY,
            value: warehouse.id?.toString(),
          })
        })
      this.warehouseSelectionModel
        .getExcludedItems()
        .forEach((warehouse) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_WAREHOUSE,
            value: warehouse.id?.toString(),
          })
        })
    }
    if (this.shelfSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_CUSTOM_SHELF, value: null })
    } else {
      this.shelfSelectionModel
        .getSelectedItems()
        .forEach((shelf) => {
          filterRules.push({
            rule_type: FILTER_HAS_CUSTOM_SHELF_ANY,
            value: shelf.id?.toString(),
          })
        })
      this.shelfSelectionModel
        .getExcludedItems()
        .forEach((shelf) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_CUSTOM_SHELF,
            value: shelf.id?.toString(),
          })
        })
    }
    if (this.boxcaseSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_BOX, value: null })
    } else {
      this.boxcaseSelectionModel
        .getSelectedItems()
        .forEach((box) => {
          filterRules.push({
            rule_type: FILTER_HAS_BOX_ANY,
            value: box.id?.toString(),
          })
        })
      this.boxcaseSelectionModel
        .getExcludedItems()
        .forEach((box) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_BOX,
            value: box.id?.toString(),
          })
        })
    }
    if (this.storagePathSelectionModel.isNoneSelected()) {
      filterRules.push({ rule_type: FILTER_STORAGE_PATH, value: null })
    } else {
      this.storagePathSelectionModel
        .getSelectedItems()
        .forEach((storagePath) => {
          filterRules.push({
            rule_type: FILTER_HAS_STORAGE_PATH_ANY,
            value: storagePath.id?.toString(),
          })
        })
      this.storagePathSelectionModel
        .getExcludedItems()
        .forEach((storagePath) => {
          filterRules.push({
            rule_type: FILTER_DOES_NOT_HAVE_STORAGE_PATH,
            value: storagePath.id?.toString(),
          })
        })
    }
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
    if (
      this.dateAddedRelativeDate !== null ||
      this.dateCreatedRelativeDate !== null
    ) {
      let queryArgs: Array<string> = []
      let existingRule = filterRules.find(
        (fr) => fr.rule_type == FILTER_FULLTEXT_QUERY
      )

      // if had a title / content search and added a relative date we need to carry it over...
      if (
        !existingRule &&
        this._textFilter?.length > 0 &&
        (this.textFilterTarget == TEXT_FILTER_TARGET_TITLE_CONTENT ||
          this.textFilterTarget == TEXT_FILTER_TARGET_TITLE)
      ) {
        existingRule = filterRules.find(
          (fr) =>
            fr.rule_type == FILTER_TITLE_CONTENT || fr.rule_type == FILTER_TITLE
        )
        existingRule.rule_type = FILTER_FULLTEXT_QUERY
      }

      let existingRuleArgs = existingRule?.value.split(',')
      if (this.dateCreatedRelativeDate !== null) {
        queryArgs.push(
          `created:[${RELATIVE_DATE_QUERYSTRINGS.find(
            (qS) => qS.relativeDate == this.dateCreatedRelativeDate
          ).dateQuery
          }]`
        )
        if (existingRule) {
          queryArgs = existingRuleArgs
            .filter((arg) => !arg.match(RELATIVE_DATE_QUERY_REGEXP_CREATED))
            .concat(queryArgs)
        }
      }
      if (this.dateAddedRelativeDate !== null) {
        queryArgs.push(
          `added:[${RELATIVE_DATE_QUERYSTRINGS.find(
            (qS) => qS.relativeDate == this.dateAddedRelativeDate
          ).dateQuery
          }]`
        )
        if (existingRule) {
          queryArgs = existingRuleArgs
            .filter((arg) => !arg.match(RELATIVE_DATE_QUERY_REGEXP_ADDED))
            .concat(queryArgs)
        }
      }

      if (existingRule) {
        existingRule.value = queryArgs.join(',')
      } else {
        filterRules.push({
          rule_type: FILTER_FULLTEXT_QUERY,
          value: queryArgs.join(','),
        })
      }
    }
    if (this.permissionsSelectionModel.ownerFilter == OwnerFilterType.SELF) {
      filterRules.push({
        rule_type: FILTER_OWNER,
        value: this.permissionsSelectionModel.userID.toString(),
      })
    } else if (
      this.permissionsSelectionModel.ownerFilter == OwnerFilterType.NOT_SELF
    ) {
      filterRules.push({
        rule_type: FILTER_OWNER_DOES_NOT_INCLUDE,
        value: this.permissionsSelectionModel.excludeUsers?.join(','),
      })
    } else if (
      this.permissionsSelectionModel.ownerFilter == OwnerFilterType.OTHERS
    ) {
      filterRules.push({
        rule_type: FILTER_OWNER_ANY,
        value: this.permissionsSelectionModel.includeUsers?.join(','),
      })
    } else if (
      this.permissionsSelectionModel.ownerFilter == OwnerFilterType.SHARED_BY_ME
    ) {
      filterRules.push({
        rule_type: FILTER_SHARED_BY_USER,
        value: this.permissionsSelectionModel.userID.toString(),
      })
    } else if (
      this.permissionsSelectionModel.ownerFilter == OwnerFilterType.UNOWNED
    ) {
      filterRules.push({
        rule_type: FILTER_OWNER_ISNULL,
        value: 'true',
      })
    }

    if (this.permissionsSelectionModel.hideUnowned) {
      filterRules.push({
        rule_type: FILTER_OWNER_ISNULL,
        value: 'false',
      })
    }
    return filterRules
  }

  @Output()
  filterRulesChange = new EventEmitter<FilterRule[]>()

  @Input()
  set selectionData(selectionData: SelectionData) {
    this.tagDocumentCounts = selectionData?.selected_tags ?? null
    this.documentTypeDocumentCounts =
      selectionData?.selected_document_types ?? null
    this.correspondentDocumentCounts =
      selectionData?.selected_correspondents ?? null
    this.storagePathDocumentCounts =
      selectionData?.selected_storage_paths ?? null
    this.warehouseDocumentCounts =
      selectionData?.selected_warehouses ?? null
    this.shelfDocumentCounts =
      selectionData?.selected_shelfs ?? null
    this.boxcaseDocumentCounts =
      selectionData?.selected_boxcases ?? null
  }

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
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Tag
      )
    ) {
      this.tagService
        .listAll()
        .subscribe((result) => (this.tags = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Correspondent
      )
    ) {
      this.correspondentService
        .listAll()
        .subscribe((result) => (this.correspondents = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.DocumentType
      )
    ) {
      this.documentTypeService
        .listAll()
        .subscribe((result) => (this.documentTypes = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.Warehouse
      )
    ) {
      // this.warehouseService
      //   .listAll(null, null, { type__iexact: 'Warehouse' })
      //   .subscribe((result) => (this.warehouses = result.results))
        
      // this.warehouseService
      //   .listAll(null, null, { type__iexact: 'Shelf' })
      //   .subscribe((result) => (this.shelfs = result.results))
      // this.warehouseService
      //   .listAll(null, null, { type__iexact: 'Boxcase' })
      //   .subscribe((result) => (this.boxcases = result.results))
      // this.warehouseService.clearCache()
      this.warehouseService.list(1,null,null,true,{type__iexact:"Warehouse"})
      .subscribe((result) => {this.warehouses = result.results;
      })
      this.warehouseService.list(1,null,null,true,{type__iexact:"Shelf"})
      .subscribe((result) => {this.shelfs = result.results;
      })
      this.warehouseService.list(1,null,null,true,{type__iexact:"Boxcase"})
      .subscribe((result) => {this.boxcases = result.results;
      })
      // this.warehouseService
      //   .listAll()
      //   .subscribe((result) => (this.warehouses = result.results))
    }
    if (
      this.permissionsService.currentUserCan(
        PermissionAction.View,
        PermissionType.StoragePath
      )
    ) {
      this.storagePathService
        .listAll()
        .subscribe((result) => (this.storagePaths = result.results))
    }

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

  toggleWarehouse(warehouseId: number) {
    this.warehouseSelectionModel.toggle(warehouseId)
  }
  toggleShelf(shelfId: number) {
    this.shelfSelectionModel.toggle(shelfId)
  }
  toggleBoxcase(boxcaseId: number) {
    this.boxcaseSelectionModel.toggle(boxcaseId)
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

  onWarehouseDropdownOpen() {
    this.warehouseSelectionModel.apply()
  }

  onShelfDropdownOpen() {
    this.shelfSelectionModel.apply()
  }

  onBoxcaseDropdownOpen() {
    this.boxcaseSelectionModel.apply()
  }

  onStoragePathDropdownOpen() {
    this.storagePathSelectionModel.apply()
  }

  updateTextFilter(text) {
    this._textFilter = text
    this.documentService.searchQuery = text
    this.updateRules()
  }

  textFilterKeyup(event: KeyboardEvent) {
    if (event.key == 'Enter') {
      const filterString = (
        this.textFilterInput.nativeElement as HTMLInputElement
      ).value
      if (filterString.length) {
        this.updateTextFilter(filterString)
      }
    } else if (event.key == 'Escape') {
      this.resetTextField()
    }
  }

  resetTextField() {
    this.updateTextFilter('')
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

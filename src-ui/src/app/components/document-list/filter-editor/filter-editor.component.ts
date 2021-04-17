import { Component, EventEmitter, Input, Output, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_ADDED_AFTER, FILTER_ADDED_BEFORE, FILTER_ASN, FILTER_CORRESPONDENT, FILTER_CREATED_AFTER, FILTER_CREATED_BEFORE, FILTER_DOCUMENT_TYPE, FILTER_FULLTEXT_MORELIKE, FILTER_FULLTEXT_QUERY, FILTER_HAS_ANY_TAG, FILTER_HAS_TAG, FILTER_TITLE, FILTER_TITLE_CONTENT } from 'src/app/data/filter-rule-type';
import { FilterableDropdownSelectionModel } from '../../common/filterable-dropdown/filterable-dropdown.component';
import { ToggleableItemState } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component';
import { DocumentService } from 'src/app/services/rest/document.service';
import { PaperlessDocument } from 'src/app/data/paperless-document';

const TEXT_FILTER_TARGET_TITLE = "title"
const TEXT_FILTER_TARGET_TITLE_CONTENT = "title-content"
const TEXT_FILTER_TARGET_ASN = "asn"
const TEXT_FILTER_TARGET_FULLTEXT_QUERY = "fulltext-query"
const TEXT_FILTER_TARGET_FULLTEXT_MORELIKE = "fulltext-morelike"

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit, OnDestroy {

  generateFilterName() {
    if (this.filterRules.length == 1) {
      let rule = this.filterRules[0]
      switch(this.filterRules[0].rule_type) {

        case FILTER_CORRESPONDENT:
          if (rule.value) {
            return $localize`Correspondent: ${this.correspondents.find(c => c.id == +rule.value)?.name}`
          } else {
            return $localize`Without correspondent`
          }

        case FILTER_DOCUMENT_TYPE:
          if (rule.value) {
            return $localize`Type: ${this.documentTypes.find(dt => dt.id == +rule.value)?.name}`
          } else {
            return $localize`Without document type`
          }

        case FILTER_HAS_TAG:
          return $localize`Tag: ${this.tags.find(t => t.id == +rule.value)?.name}`

        case FILTER_HAS_ANY_TAG:
          if (rule.value == "false") {
            return $localize`Without any tag`
          }

        case FILTER_TITLE:
          return $localize`Title: ${rule.value}`

        case FILTER_ASN:
          return $localize`ASN: ${rule.value}`
      }
    }

    return ""
  }

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    private documentService: DocumentService
  ) { }

  @ViewChild("textFilterInput")
  textFilterInput: ElementRef

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[] = []
  documentTypes: PaperlessDocumentType[] = []

  _textFilter = ""
  _moreLikeId: number
  _moreLikeDoc: PaperlessDocument

  get textFilterTargets() {
    let targets = [
      {id: TEXT_FILTER_TARGET_TITLE, name: $localize`Title`},
      {id: TEXT_FILTER_TARGET_TITLE_CONTENT, name: $localize`Title & content`},
      {id: TEXT_FILTER_TARGET_ASN, name: $localize`ASN`},
      {id: TEXT_FILTER_TARGET_FULLTEXT_QUERY, name: $localize`Advanced search`}
    ]
    if (this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE) {
      targets.push({id: TEXT_FILTER_TARGET_FULLTEXT_MORELIKE, name: $localize`More like`})
    }
    return targets
  }

  textFilterTarget = TEXT_FILTER_TARGET_TITLE_CONTENT

  get textFilterTargetName() {
    return this.textFilterTargets.find(t => t.id == this.textFilterTarget)?.name
  }


  tagSelectionModel = new FilterableDropdownSelectionModel()
  correspondentSelectionModel = new FilterableDropdownSelectionModel()
  documentTypeSelectionModel = new FilterableDropdownSelectionModel()

  dateCreatedBefore: string
  dateCreatedAfter: string
  dateAddedBefore: string
  dateAddedAfter: string

  _unmodifiedFilterRules: FilterRule[] = []
  _filterRules: FilterRule[] = []

  @Input()
  set unmodifiedFilterRules(value: FilterRule[]) {
    this._unmodifiedFilterRules = value
    this.checkIfRulesHaveChanged()
  }

  get unmodifiedFilterRules(): FilterRule[] {
    return this._unmodifiedFilterRules
  }

  @Input()
  set filterRules (value: FilterRule[]) {
    this._filterRules = value

    this.documentTypeSelectionModel.clear(false)
    this.tagSelectionModel.clear(false)
    this.correspondentSelectionModel.clear(false)
    this._textFilter = null
    this._moreLikeId = null
    this.dateAddedBefore = null
    this.dateAddedAfter = null
    this.dateCreatedBefore = null
    this.dateCreatedAfter = null

    value.forEach(rule => {
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
          this.documentService.get(this._moreLikeId).subscribe(result => {
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
        case FILTER_HAS_TAG:
          this.tagSelectionModel.set(rule.value ? +rule.value : null, ToggleableItemState.Selected, false)
          break
        case FILTER_HAS_ANY_TAG:
          this.tagSelectionModel.set(null, ToggleableItemState.Selected, false)
          break
        case FILTER_CORRESPONDENT:
          this.correspondentSelectionModel.set(rule.value ? +rule.value : null, ToggleableItemState.Selected, false)
          break
        case FILTER_DOCUMENT_TYPE:
          this.documentTypeSelectionModel.set(rule.value ? +rule.value : null, ToggleableItemState.Selected, false)
          break
      }
    })
    this.checkIfRulesHaveChanged()
  }

  get filterRules(): FilterRule[] {
    let filterRules: FilterRule[] = []
    if (this._textFilter && this.textFilterTarget == TEXT_FILTER_TARGET_TITLE_CONTENT) {
      filterRules.push({rule_type: FILTER_TITLE_CONTENT, value: this._textFilter})
    }
    if (this._textFilter && this.textFilterTarget == TEXT_FILTER_TARGET_TITLE) {
      filterRules.push({rule_type: FILTER_TITLE, value: this._textFilter})
    }
    if (this._textFilter && this.textFilterTarget == TEXT_FILTER_TARGET_ASN) {
      filterRules.push({rule_type: FILTER_ASN, value: this._textFilter})
    }
    if (this._textFilter && this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_QUERY) {
      filterRules.push({rule_type: FILTER_FULLTEXT_QUERY, value: this._textFilter})
    }
    if (this._moreLikeId && this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE) {
      filterRules.push({rule_type: FILTER_FULLTEXT_MORELIKE, value: this._moreLikeId?.toString()})
    }
    if (this.tagSelectionModel.isNoneSelected()) {
      filterRules.push({rule_type: FILTER_HAS_ANY_TAG, value: "false"})
    } else {
      this.tagSelectionModel.getSelectedItems().filter(tag => tag.id).forEach(tag => {
        filterRules.push({rule_type: FILTER_HAS_TAG, value: tag.id?.toString()})
      })
    }
    this.correspondentSelectionModel.getSelectedItems().forEach(correspondent => {
      filterRules.push({rule_type: FILTER_CORRESPONDENT, value: correspondent.id?.toString()})
    })
    this.documentTypeSelectionModel.getSelectedItems().forEach(documentType => {
      filterRules.push({rule_type: FILTER_DOCUMENT_TYPE, value: documentType.id?.toString()})
    })
    if (this.dateCreatedBefore) {
      filterRules.push({rule_type: FILTER_CREATED_BEFORE, value: this.dateCreatedBefore})
    }
    if (this.dateCreatedAfter) {
      filterRules.push({rule_type: FILTER_CREATED_AFTER, value: this.dateCreatedAfter})
    }
    if (this.dateAddedBefore) {
      filterRules.push({rule_type: FILTER_ADDED_BEFORE, value: this.dateAddedBefore})
    }
    if (this.dateAddedAfter) {
      filterRules.push({rule_type: FILTER_ADDED_AFTER, value: this.dateAddedAfter})
    }
    return filterRules
  }

  @Output()
  filterRulesChange = new EventEmitter<FilterRule[]>()

  rulesModified: boolean = false

  private checkIfRulesHaveChanged() {
    let modified = false
    if (this._unmodifiedFilterRules.length != this._filterRules.length) {
      modified = true
    } else {
      modified = this._unmodifiedFilterRules.some(rule => {
        return (this._filterRules.find(fri => fri.rule_type == rule.rule_type && fri.value == rule.value) == undefined)
      })

      if (!modified) {
        // only check other direction if we havent already determined is modified
        modified = this._filterRules.some(rule => {
          this._unmodifiedFilterRules.find(fr => fr.rule_type == rule.rule_type && fr.value == rule.value) == undefined
        })
      }
    }
    this.rulesModified = modified
  }

  updateRules() {
    this.filterRulesChange.next(this.filterRules)
  }

  get textFilter() {
    return this._textFilter
  }

  set textFilter(value) {
    this.textFilterDebounce.next(value)
  }

  textFilterDebounce: Subject<string>
  subscription: Subscription

  ngOnInit() {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)

    this.textFilterDebounce = new Subject<string>()

    this.subscription = this.textFilterDebounce.pipe(
      debounceTime(400),
      distinctUntilChanged()
    ).subscribe(text => {
      this._textFilter = text
      this.documentService.searchQuery = text
      this.updateRules()
    })

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

  onTagsDropdownOpen() {
    this.tagSelectionModel.apply()
  }

  onCorrespondentDropdownOpen() {
    this.correspondentSelectionModel.apply()
  }

  onDocumentTypeDropdownOpen() {
    this.documentTypeSelectionModel.apply()
  }

  changeTextFilterTarget(target) {
    if (this.textFilterTarget == TEXT_FILTER_TARGET_FULLTEXT_MORELIKE && target != TEXT_FILTER_TARGET_FULLTEXT_MORELIKE) {
      this._textFilter = ""
    }
    this.textFilterTarget = target
    this.textFilterInput.nativeElement.focus()
    this.updateRules()
  }
}

import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_ADDED_AFTER, FILTER_ADDED_BEFORE, FILTER_CORRESPONDENT, FILTER_CREATED_AFTER, FILTER_CREATED_BEFORE, FILTER_DOCUMENT_TYPE, FILTER_HAS_ANY_TAG, FILTER_HAS_TAG, FILTER_DOES_NOT_HAVE_TAG, FILTER_TITLE } from 'src/app/data/filter-rule-type';
import { FilterableDropdownSelectionModel } from '../../common/filterable-dropdown/filterable-dropdown.component';
import { ToggleableItemState } from '../../common/filterable-dropdown/toggleable-dropdown-button/toggleable-dropdown-button.component';

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

      }
    }

    return ""
  }

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService
  ) { }

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[] = []
  documentTypes: PaperlessDocumentType[] = []

  _titleFilter = ""

  tagSelectionModel = new FilterableDropdownSelectionModel()
  correspondentSelectionModel = new FilterableDropdownSelectionModel()
  documentTypeSelectionModel = new FilterableDropdownSelectionModel()

  dateCreatedBefore: string
  dateCreatedAfter: string
  dateAddedBefore: string
  dateAddedAfter: string

  @Input()
  set filterRules (value: FilterRule[]) {
    this.documentTypeSelectionModel.clear(false)
    this.tagSelectionModel.clear(false)
    this.correspondentSelectionModel.clear(false)
    this._titleFilter = null
    this.dateAddedBefore = null
    this.dateAddedAfter = null
    this.dateCreatedBefore = null
    this.dateCreatedAfter = null

    value.forEach(rule => {
      switch (rule.rule_type) {
        case FILTER_TITLE:
          this._titleFilter = rule.value
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
        case FILTER_DOES_NOT_HAVE_TAG:
          this.tagSelectionModel.set(rule.value ? +rule.value : null, ToggleableItemState.Excluded, false)
          break
        case FILTER_CORRESPONDENT:
          this.correspondentSelectionModel.set(rule.value ? +rule.value : null, ToggleableItemState.Selected, false)
          break
        case FILTER_DOCUMENT_TYPE:
          this.documentTypeSelectionModel.set(rule.value ? +rule.value : null, ToggleableItemState.Selected, false)
          break
      }
    })
  }

  get filterRules() {
    let filterRules: FilterRule[] = []
    if (this._titleFilter) {
      filterRules.push({rule_type: FILTER_TITLE, value: this._titleFilter})
    }
    if (this.tagSelectionModel.isNoneSelected()) {
      filterRules.push({rule_type: FILTER_HAS_ANY_TAG, value: "false"})
    } else {
      this.tagSelectionModel.getSelectedItems().filter(tag => tag.id).forEach(tag => {
        filterRules.push({rule_type: FILTER_HAS_TAG, value: tag.id?.toString()})
      })
      this.tagSelectionModel.getExcludedItems().filter(tag => tag.id).forEach(tag => {
        filterRules.push({rule_type: FILTER_DOES_NOT_HAVE_TAG, value: tag.id?.toString()})
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

  @Output()
  reset = new EventEmitter()

  @Input()
  rulesModified: boolean = false

  updateRules() {
    this.filterRulesChange.next(this.filterRules)
  }

  get titleFilter() {
    return this._titleFilter
  }

  set titleFilter(value) {
    this.titleFilterDebounce.next(value)
  }

  titleFilterDebounce: Subject<string>
  subscription: Subscription

  ngOnInit() {
    this.tagService.listAll().subscribe(result => this.tags = result.results)
    this.correspondentService.listAll().subscribe(result => this.correspondents = result.results)
    this.documentTypeService.listAll().subscribe(result => this.documentTypes = result.results)

    this.titleFilterDebounce = new Subject<string>()

    this.subscription = this.titleFilterDebounce.pipe(
      debounceTime(400),
      distinctUntilChanged()
    ).subscribe(title => {
      this._titleFilter = title
      this.updateRules()
    })
  }

  ngOnDestroy() {
    this.titleFilterDebounce.complete()
  }

  resetSelected() {
    this.reset.next()
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
}

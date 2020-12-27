import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged, filter, flatMap, mergeMap } from 'rxjs/operators';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_ADDED_AFTER, FILTER_ADDED_BEFORE, FILTER_CORRESPONDENT, FILTER_CREATED_AFTER, FILTER_CREATED_BEFORE, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES, FILTER_TITLE } from 'src/app/data/filter-rule-type';
import { FilterableDropdownSelectionModel } from '../../common/filterable-dropdown/filterable-dropdown.component';

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
          return `Correspondent: ${this.correspondents.find(c => c.id == +rule.value)?.name}`

        case FILTER_DOCUMENT_TYPE:
          return `Type: ${this.documentTypes.find(dt => dt.id == +rule.value)?.name}`

        case FILTER_HAS_TAG:
          return `Tag: ${this.tags.find(t => t.id == +rule.value)?.name}`

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
    console.log("SET FILTER RULES")
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
      }
    })

    this.tagService.getCachedMany(value.filter(v => v.rule_type == FILTER_HAS_TAG).map(rule => +rule.value)).subscribe(tags => {
      console.log(tags)
      tags.forEach(tag => this.tagSelectionModel.toggle(tag, false))
    })
  }

  @Output()
  filterRulesChange = new EventEmitter<FilterRule[]>()

  updateRules() {
    console.log("UPDATE RULES!!!")
    let filterRules: FilterRule[] = []
    if (this._titleFilter) {
      filterRules.push({rule_type: FILTER_TITLE, value: this._titleFilter})
    }
    this.tagSelectionModel.getSelected().forEach(tag => {
      filterRules.push({rule_type: FILTER_HAS_TAG, value: tag.id.toString()})
    })
    this.correspondentSelectionModel.getSelected().forEach(correspondent => {
      filterRules.push({rule_type: FILTER_CORRESPONDENT, value: correspondent.id.toString()})
    })
    this.documentTypeSelectionModel.getSelected().forEach(documentType => {
      filterRules.push({rule_type: FILTER_DOCUMENT_TYPE, value: documentType.id.toString()})
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
    console.log(filterRules)
    this.filterRulesChange.next(filterRules)
  }

  hasFilters() {
    return this._titleFilter || 
      this.dateCreatedAfter || this.dateAddedBefore || this.dateCreatedAfter || this.dateCreatedBefore ||
      this.tagSelectionModel.selectionSize() || this.correspondentSelectionModel.selectionSize() || this.documentTypeSelectionModel.selectionSize()
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

  clearSelected() {
    this._titleFilter = ""
    this.updateRules()
  }

  toggleTag(tagId: number) {
  }

  toggleCorrespondent(correspondentId: number) {
  }

  toggleDocumentType(documentTypeId: number) {
  }

}

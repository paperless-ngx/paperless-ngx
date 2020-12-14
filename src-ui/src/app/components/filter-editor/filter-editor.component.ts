import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_ADDED_AFTER, FILTER_ADDED_BEFORE, FILTER_CORRESPONDENT, FILTER_CREATED_AFTER, FILTER_CREATED_BEFORE, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES, FILTER_TITLE } from 'src/app/data/filter-rule-type';

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit, OnDestroy {

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService
  ) { }

  tags: PaperlessTag[] = []
  correspondents: PaperlessCorrespondent[]
  documentTypes: PaperlessDocumentType[] = []

  @Input()
  filterRules: FilterRule[]

  @Output()
  filterRulesChange = new EventEmitter<FilterRule[]>()
  
  hasFilters() {
    return this.filterRules.length > 0
  }

  get selectedTags(): PaperlessTag[] {
    let tagRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_HAS_TAG)
    return this.tags?.filter(t => tagRules.find(tr => tr.value == t.id))
  }

  get selectedCorrespondents(): PaperlessCorrespondent[] {
    let correspondentRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_CORRESPONDENT)
    return this.correspondents?.filter(c => correspondentRules.find(cr => cr.value == c.id))
  }

  get selectedDocumentTypes(): PaperlessDocumentType[] {
    let documentTypeRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_DOCUMENT_TYPE)
    return this.documentTypes?.filter(dt => documentTypeRules.find(dtr => dtr.value == dt.id))
  }

  get titleFilter() {
    let existingRule = this.filterRules.find(rule => rule.rule_type == FILTER_TITLE)
    return existingRule ? existingRule.value : ''
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
      
      this.setTitleRule(title)
    })
  }

  ngOnDestroy() {
    this.titleFilterDebounce.complete()
    // TODO: not sure if both is necessary
    this.subscription.unsubscribe()
  }

  applyFilters() {
    this.filterRulesChange.next(this.filterRules)
  }

  clearSelected() {
    this.filterRules = []
    this.applyFilters()
  }

  private toggleFilterRule(filterRuleTypeID: number, value: number) {

    let filterRuleType = FILTER_RULE_TYPES.find(t => t.id == filterRuleTypeID)

    let existingRule = this.filterRules.find(rule => rule.rule_type == filterRuleTypeID && rule.value == value)
    let existingRuleOfSameType = this.filterRules.find(rule => rule.rule_type == filterRuleTypeID)
    
    if (existingRule) {
      // if this exact rule already exists, remove it in all cases.
      this.filterRules.splice(this.filterRules.indexOf(existingRule), 1)
    } else if (filterRuleType.multi || !existingRuleOfSameType) {
      // if we allow multiple rules per type, or no rule of this type already exists, push a new rule.
      this.filterRules.push({rule_type: filterRuleTypeID, value: value})
    } else {
      // otherwise (i.e., no multi support AND there's already a rule of this type), update the rule.
      existingRuleOfSameType.value = value
    }
    this.applyFilters()
  }

  private setTitleRule(title: string) {
    let existingRule = this.filterRules.find(rule => rule.rule_type == FILTER_TITLE)

    if (!existingRule && title) {
      this.filterRules.push({rule_type: FILTER_TITLE, value: title})
    } else if (existingRule && !title) {
      this.filterRules.splice(this.filterRules.findIndex(rule => rule.rule_type == FILTER_TITLE), 1)
    } else if (existingRule && title) {
      existingRule.value = title
    }
    this.applyFilters()
  }

  toggleTag(tagId: number) {
    this.toggleFilterRule(FILTER_HAS_TAG, tagId)
  }

  toggleCorrespondent(correspondentId: number) {
    this.toggleFilterRule(FILTER_CORRESPONDENT, correspondentId)
  }

  toggleDocumentType(documentTypeId: number) {
    this.toggleFilterRule(FILTER_DOCUMENT_TYPE, documentTypeId)
  }



  // Date handling


  onDateCreatedBeforeSet(date: NgbDateStruct) {
    this.setDateCreatedBefore(date)
    this.applyFilters()
  }

  onDateCreatedAfterSet(date: NgbDateStruct) {
    this.setDateCreatedAfter(date)
    this.applyFilters()
  }

  onDateAddedBeforeSet(date: NgbDateStruct) {
    this.setDateAddedBefore(date)
    this.applyFilters()
  }

  onDateAddedAfterSet(date: NgbDateStruct) {
    this.setDateAddedAfter(date)
    this.applyFilters()
  }

  get dateCreatedBefore(): NgbDateStruct {
    let createdBeforeRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_CREATED_BEFORE)
    return createdBeforeRule ? {
      year: createdBeforeRule.value.substring(0,4),
      month: createdBeforeRule.value.substring(5,7),
      day: createdBeforeRule.value.substring(8,10)
    } : undefined
  }

  get dateCreatedAfter(): NgbDateStruct {
    let createdAfterRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_CREATED_AFTER)
    return createdAfterRule ? {
      year: createdAfterRule.value.substring(0,4),
      month: createdAfterRule.value.substring(5,7),
      day: createdAfterRule.value.substring(8,10)
    } : undefined
  }

  get dateAddedBefore(): NgbDateStruct {
    let addedBeforeRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_ADDED_BEFORE)
    return addedBeforeRule ? {
      year: addedBeforeRule.value.substring(0,4),
      month: addedBeforeRule.value.substring(5,7),
      day: addedBeforeRule.value.substring(8,10)
    } : undefined
  }

  get dateAddedAfter(): NgbDateStruct {
    let addedAfterRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_ADDED_AFTER)
    return addedAfterRule ? {
      year: addedAfterRule.value.substring(0,4),
      month: addedAfterRule.value.substring(5,7),
      day: addedAfterRule.value.substring(8,10)
    } : undefined
  }

  setDateCreatedBefore(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_CREATED_BEFORE)
    else this.clearDateFilter(FILTER_CREATED_BEFORE)
  }

  setDateCreatedAfter(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_CREATED_AFTER)
    else this.clearDateFilter(FILTER_CREATED_AFTER)
  }

  setDateAddedBefore(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_ADDED_BEFORE)
    else this.clearDateFilter(FILTER_ADDED_BEFORE)
  }

  setDateAddedAfter(date?: NgbDateStruct) {
    if (date) this.setDateFilter(date, FILTER_ADDED_AFTER)
    else this.clearDateFilter(FILTER_ADDED_AFTER)
  }

  setDateFilter(date: NgbDateStruct, dateRuleTypeID: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.rule_type == dateRuleTypeID)
    let newValue = `${date.year}-${date.month.toString().padStart(2,'0')}-${date.day.toString().padStart(2,'0')}` // YYYY-MM-DD

    if (existingRule) {
      existingRule.value = newValue
    } else {
      filterRules.push({rule_type: dateRuleTypeID, value: newValue})
    }

    this.filterRules = filterRules
  }

  clearDateFilter(dateRuleTypeID: number) {
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.rule_type == dateRuleTypeID)
    filterRules.splice(filterRules.indexOf(existingRule), 1)
    this.filterRules = filterRules
  }

}

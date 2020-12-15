import { Component, EventEmitter, Input, Output, OnInit, OnDestroy } from '@angular/core';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { Subject, Subscription } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { NgbDateParserFormatter, NgbDateStruct } from '@ng-bootstrap/ng-bootstrap';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { FilterRule } from 'src/app/data/filter-rule';
import { FILTER_ADDED_AFTER, FILTER_ADDED_BEFORE, FILTER_CORRESPONDENT, FILTER_CREATED_AFTER, FILTER_CREATED_BEFORE, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_RULE_TYPES, FILTER_TITLE } from 'src/app/data/filter-rule-type';
import { DateSelection } from './filter-dropdown-date/filter-dropdown-date.component';

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit, OnDestroy {

  constructor(
    private documentTypeService: DocumentTypeService,
    private tagService: TagService,
    private correspondentService: CorrespondentService,
    private dateParser: NgbDateParserFormatter
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
    return this.tags?.filter(t => tagRules.find(tr => +tr.value == t.id))
  }

  get selectedCorrespondents(): PaperlessCorrespondent[] {
    let correspondentRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_CORRESPONDENT)
    return this.correspondents?.filter(c => correspondentRules.find(cr => +cr.value == c.id))
  }

  get selectedDocumentTypes(): PaperlessDocumentType[] {
    let documentTypeRules: FilterRule[] = this.filterRules.filter(fr => fr.rule_type == FILTER_DOCUMENT_TYPE)
    return this.documentTypes?.filter(dt => documentTypeRules.find(dtr => +dtr.value == dt.id))
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

    let existingRule = this.filterRules.find(rule => rule.rule_type == filterRuleTypeID && rule.value == value?.toString())
    let existingRuleOfSameType = this.filterRules.find(rule => rule.rule_type == filterRuleTypeID)
    
    if (existingRule) {
      // if this exact rule already exists, remove it in all cases.
      this.filterRules.splice(this.filterRules.indexOf(existingRule), 1)
    } else if (filterRuleType.multi || !existingRuleOfSameType) {
      // if we allow multiple rules per type, or no rule of this type already exists, push a new rule.
      this.filterRules.push({rule_type: filterRuleTypeID, value: value?.toString()})
    } else {
      // otherwise (i.e., no multi support AND there's already a rule of this type), update the rule.
      existingRuleOfSameType.value = value?.toString()
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


  onDatesCreatedSet(dates: DateSelection) {
    this.setDateCreatedBefore(dates.before)
    this.setDateCreatedAfter(dates.after)
    this.applyFilters()
  }

  onDatesAddedSet(dates: DateSelection) {
    this.setDateAddedBefore(dates.before)
    this.setDateAddedAfter(dates.after)
    this.applyFilters()
  }

  get dateCreatedBefore(): NgbDateStruct {
    let createdBeforeRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_CREATED_BEFORE)
    return createdBeforeRule ? this.dateParser.parse(createdBeforeRule.value) : null
  }

  get dateCreatedAfter(): NgbDateStruct {
    let createdAfterRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_CREATED_AFTER)
    return createdAfterRule ? this.dateParser.parse(createdAfterRule.value) : null
  }

  get dateAddedBefore(): NgbDateStruct {
    let addedBeforeRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_ADDED_BEFORE)
    return addedBeforeRule ? this.dateParser.parse(addedBeforeRule.value) : null
  }

  get dateAddedAfter(): NgbDateStruct {
    let addedAfterRule: FilterRule = this.filterRules.find(fr => fr.rule_type == FILTER_ADDED_AFTER)
    return addedAfterRule ? this.dateParser.parse(addedAfterRule.value) : null
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
    let newValue = this.dateParser.format(date)

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

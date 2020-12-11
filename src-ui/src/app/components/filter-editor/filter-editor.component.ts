import { Component, EventEmitter, Input, OnInit, Output, ElementRef, AfterViewInit, QueryList, ViewChild, ViewChildren } from '@angular/core';
import { FilterRule } from 'src/app/data/filter-rule';
import { FilterRuleType, FILTER_RULE_TYPES, FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE, FILTER_HAS_TAG, FILTER_TITLE, FILTER_ADDED_BEFORE, FILTER_ADDED_AFTER, FILTER_CREATED_BEFORE, FILTER_CREATED_AFTER, FILTER_CREATED_YEAR, FILTER_CREATED_MONTH, FILTER_CREATED_DAY } from 'src/app/data/filter-rule-type';
import { PaperlessCorrespondent } from 'src/app/data/paperless-correspondent';
import { PaperlessDocumentType } from 'src/app/data/paperless-document-type';
import { PaperlessTag } from 'src/app/data/paperless-tag';
import { AbstractPaperlessService } from 'src/app/services/rest/abstract-paperless-service';
import { ObjectWithId } from 'src/app/data/object-with-id';
import { CorrespondentService } from 'src/app/services/rest/correspondent.service';
import { DocumentTypeService } from 'src/app/services/rest/document-type.service';
import { TagService } from 'src/app/services/rest/tag.service';
import { FilterDropdownComponent } from './filter-dropdown/filter-dropdown.component'
import { fromEvent } from 'rxjs';
import { debounceTime, distinctUntilChanged, tap } from 'rxjs/operators';

@Component({
  selector: 'app-filter-editor',
  templateUrl: './filter-editor.component.html',
  styleUrls: ['./filter-editor.component.scss']
})
export class FilterEditorComponent implements OnInit, AfterViewInit {

  constructor(private documentTypeService: DocumentTypeService, private tagService: TagService, private correspondentService: CorrespondentService) { }

  @Output()
  clear = new EventEmitter()

  @Input()
  filterRules: FilterRule[] = []

  @Output()
  apply = new EventEmitter()

  @ViewChild('filterTextInput') filterTextInput: ElementRef;
  @ViewChildren(FilterDropdownComponent) quickFilterDropdowns!: QueryList<FilterDropdownComponent>;

  quickFilterRuleTypeIDs: number[] = [FILTER_HAS_TAG, FILTER_CORRESPONDENT, FILTER_DOCUMENT_TYPE]
  dateAddedFilterRuleTypeIDs: any[] = [[FILTER_ADDED_BEFORE, FILTER_ADDED_AFTER], [FILTER_CREATED_BEFORE, FILTER_CREATED_AFTER, FILTER_CREATED_YEAR, FILTER_CREATED_MONTH, FILTER_CREATED_DAY]]

  correspondents: PaperlessCorrespondent[] = []
  tags: PaperlessTag[] = []
  documentTypes: PaperlessDocumentType[] = []

  filterText: string
  filterTagsText: string
  filterCorrespondentsText: string
  filterDocumentTypesText: string

  ngOnInit(): void {
    this.updateTextFilterInput()
    this.tagService.listAll().subscribe(result => this.setDropdownItems(result.results, FILTER_HAS_TAG))
    this.correspondentService.listAll().subscribe(result => this.setDropdownItems(result.results, FILTER_CORRESPONDENT))
    this.documentTypeService.listAll().subscribe(result => this.setDropdownItems(result.results, FILTER_DOCUMENT_TYPE))
  }

  ngAfterViewInit() {
    fromEvent(this.filterTextInput.nativeElement,'keyup')
        .pipe(
            debounceTime(150),
            distinctUntilChanged(),
            tap()
        )
        .subscribe((event: Event) => {
          this.filterText = (event.target as HTMLInputElement).value
          this.onTextFilterInput()
        });
  }

  setDropdownItems(items: ObjectWithId[], filterRuleTypeID: number): void {
    let dropdown: FilterDropdownComponent = this.getDropdownByFilterRuleTypeID(filterRuleTypeID)
    if (dropdown) {
      dropdown.items = items
    }
    this.updateDropdownActiveItems(dropdown)
  }

  updateDropdownActiveItems(dropdown: FilterDropdownComponent): void {
    let activeRulesValues = this.filterRules.filter(r => r.type.id == dropdown.filterRuleTypeID).map(r => r.value)
    let activeItems = []
    if (activeRulesValues.length > 0) {
      activeItems = dropdown.items.filter(i => activeRulesValues.includes(i.id))
    }
    dropdown.itemsActive = activeItems
  }

  getDropdownByFilterRuleTypeID(filterRuleTypeID: number): FilterDropdownComponent {
    return this.quickFilterDropdowns.find(d => d.filterRuleTypeID == filterRuleTypeID)
  }

  applySelected() {
    this.apply.next()
  }

  clearSelected() {
    this.filterRules.splice(0,this.filterRules.length)
    this.updateTextFilterInput()
    this.quickFilterDropdowns.forEach(d => this.updateDropdownActiveItems(d))
    this.clear.next()
  }

  hasFilters() {
    return this.filterRules.length > 0
  }

  updateTextFilterInput() {
    let existingTextRule = this.filterRules.find(rule => rule.type.id == FILTER_TITLE)
    if (existingTextRule) this.filterText = existingTextRule.value
    else this.filterText = ''
  }

  onTextFilterInput() {
    let text = this.filterText
    let filterRules = this.filterRules
    let existingRule = filterRules.find(rule => rule.type.id == FILTER_TITLE)
    if (existingRule && existingRule.value == text) {
      return
    } else if (existingRule) {
      existingRule.value = text
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == FILTER_TITLE), value: text})
    }
    this.filterRules = filterRules
    this.applySelected()
  }

  toggleFilterByItem(item: ObjectWithId, filterRuleTypeID: number) {
    let filterRules = this.filterRules
    let filterRuleType: FilterRuleType = FILTER_RULE_TYPES.find(t => t.id == filterRuleTypeID)
    let existingRule = filterRules.find(rule => rule.type.id == filterRuleType.id)

    if (existingRule && existingRule.value == item.id) {
      filterRules.splice(filterRules.indexOf(existingRule), 1)
    } else if (existingRule && filterRuleType.id == FILTER_HAS_TAG) {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == filterRuleType.id), value: item.id})
    } else if (existingRule && existingRule.value == item.id) {
      return
    } else if (existingRule) {
      existingRule.value = item.id
    } else {
      filterRules.push({type: FILTER_RULE_TYPES.find(t => t.id == filterRuleType.id), value: item.id})
    }

    let dropdown = this.getDropdownByFilterRuleTypeID(filterRuleTypeID)
    this.updateDropdownActiveItems(dropdown)

    this.filterRules = filterRules
    this.applySelected()
  }

}

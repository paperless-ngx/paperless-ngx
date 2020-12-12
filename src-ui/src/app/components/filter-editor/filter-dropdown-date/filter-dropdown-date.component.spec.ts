import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterDropdownDateComponent } from './filter-dropdown-date.component';

describe('FilterDropdownDateComponent', () => {
  let component: FilterDropdownDateComponent;
  let fixture: ComponentFixture<FilterDropdownDateComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FilterDropdownDateComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(FilterDropdownDateComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

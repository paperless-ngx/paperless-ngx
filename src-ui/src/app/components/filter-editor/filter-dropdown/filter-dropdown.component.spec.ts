import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterDropodownComponent } from './filter-dropdown.component';

describe('FilterDropodownComponent', () => {
  let component: FilterDropodownComponent;
  let fixture: ComponentFixture<FilterDropodownComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FilterDropodownComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(FilterDropodownComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

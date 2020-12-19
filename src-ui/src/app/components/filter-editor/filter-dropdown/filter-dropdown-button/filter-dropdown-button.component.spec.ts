import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterDropodownButtonComponent } from './filter-dropdown-button.component';

describe('FilterDropodownButtonComponent', () => {
  let component: FilterDropodownButtonComponent;
  let fixture: ComponentFixture<FilterDropodownButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FilterDropodownButtonComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(FilterDropodownButtonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

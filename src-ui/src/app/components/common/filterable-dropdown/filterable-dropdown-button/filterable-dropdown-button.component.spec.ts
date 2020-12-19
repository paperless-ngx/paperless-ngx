import { ComponentFixture, TestBed } from '@angular/core/testing';

import { FilterableDropodownButtonComponent } from './filterable-dropdown-button.component';

describe('FilterableDropodownButtonComponent', () => {
  let component: FilterableDropodownButtonComponent;
  let fixture: ComponentFixture<FilterableDropodownButtonComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ FilterableDropodownButtonComponent ]
    })
    .compileComponents();
  });

  beforeEach(() => {
    fixture = TestBed.createComponent(FilterableDropodownButtonComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});

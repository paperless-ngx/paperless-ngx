describe('tasks', () => {
  beforeEach(() => {
    this.dismissedTasks = new Set<number>()

    cy.fixture('tasks/tasks.json').then((tasksViewsJson) => {
      // acknowledge tasks POST
      cy.intercept(
        'POST',
        'http://localhost:8000/api/acknowledge_tasks/',
        (req) => {
          req.body['tasks'].forEach((t) => this.dismissedTasks.add(t)) // store this for later
          req.reply({ result: 'OK' })
        }
      )

      cy.intercept('GET', 'http://localhost:8000/api/tasks/', (req) => {
        let response = [...tasksViewsJson]
        if (this.dismissedTasks.size) {
          response = response.filter((t) => {
            return !this.dismissedTasks.has(t.id)
          })
        }

        req.reply(response)
      }).as('tasks')
    })

    cy.visit('/tasks')
    cy.wait('@tasks')
  })

  it('should show a list of dismissable tasks in tabs', () => {
    cy.get('tbody').find('tr:visible').its('length').should('eq', 10) // double because collapsible result tr
    cy.wait(500) // stabilizes the test, for some reason...
    cy.get('tbody')
      .find('button:visible')
      .contains('Dismiss')
      .first()
      .click()
      .wait('@tasks')
      .wait(2000)
      .then(() => {
        cy.get('tbody').find('tr:visible').its('length').should('eq', 8) // double because collapsible result tr
      })
  })

  it('should allow toggling all tasks in list and warn on dismiss', () => {
    cy.get('thead').find('input[type="checkbox"]').first().click()
    cy.get('body').find('button').contains('Dismiss selected').first().click()
    cy.contains('Confirm')
    cy.get('.modal')
      .contains('button', 'Dismiss')
      .click()
      .wait('@tasks')
      .wait(2000)
      .then(() => {
        cy.get('tbody').find('tr:visible').should('not.exist')
      })
  })
})

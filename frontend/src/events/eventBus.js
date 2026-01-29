/**
 * Event Bus - Event-Driven Architecture
 * 
 * Lightweight pub/sub system for decoupled component communication
 */

class EventBus {
    constructor() {
        this.events = {}
    }

    /**
     * Subscribe to an event
     */
    on(event, callback) {
        if (!this.events[event]) {
            this.events[event] = []
        }
        this.events[event].push(callback)

        // Return unsubscribe function
        return () => this.off(event, callback)
    }

    /**
     * Unsubscribe from an event
     */
    off(event, callback) {
        if (!this.events[event]) return
        this.events[event] = this.events[event].filter(cb => cb !== callback)
    }

    /**
     * Emit an event with data
     */
    emit(event, data) {
        if (!this.events[event]) return
        this.events[event].forEach(callback => callback(data))
    }

    /**
     * Subscribe to event once
     */
    once(event, callback) {
        const unsubscribe = this.on(event, (data) => {
            callback(data)
            unsubscribe()
        })
    }
}

// Singleton instance
export const eventBus = new EventBus()

// Event types for type safety
export const Events = {
    SEARCH_START: 'search:start',
    SEARCH_COMPLETE: 'search:complete',
    SEARCH_ERROR: 'search:error',
    DEAL_FAVORITE: 'deal:favorite',
    DEAL_SHARE: 'deal:share',
    DEAL_CLICK: 'deal:click',
}

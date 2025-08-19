"use client"

import { useState } from "react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"
import { Switch } from "@/components/ui/switch"
import { Separator } from "@/components/ui/separator"
import { 
  Plus, 
  Trash2, 
  MessageSquare, 
  Zap, 
  GitBranch, 
  Move, 
  Database,
  Settings 
} from "lucide-react"
import ModelSelector from "@/components/playground/ModelSelector"

interface WorkflowStep {
  id: string
  name: string
  type: string
  config: Record<string, any>
  position: { x: number; y: number }
  connections: string[]
}

interface StepConfigurationPanelProps {
  step: WorkflowStep
  onUpdateStep: (stepId: string, updates: Partial<WorkflowStep>) => void
  availableVariables: string[]
  availableChatbots: Array<{id: string, name: string}>
  availableCollections: string[]
}

export default function StepConfigurationPanel({
  step,
  onUpdateStep,
  availableVariables = [],
  availableChatbots = [],
  availableCollections = []
}: StepConfigurationPanelProps) {
  
  const updateConfig = (key: string, value: any) => {
    onUpdateStep(step.id, {
      config: { ...(step.config || {}), [key]: value }
    })
  }

  const addMessage = () => {
    const messages = step.config?.messages || []
    updateConfig('messages', [
      ...messages,
      { role: 'user', content: '' }
    ])
  }

  const updateMessage = (index: number, field: string, value: string) => {
    const messages = [...(step.config?.messages || [])]
    messages[index] = { ...messages[index], [field]: value }
    updateConfig('messages', messages)
  }

  const removeMessage = (index: number) => {
    const messages = step.config?.messages || []
    updateConfig('messages', messages.filter((_, i) => i !== index))
  }

  const addCondition = () => {
    const conditions = step.config?.conditions || []
    updateConfig('conditions', [...conditions, ''])
  }

  const updateCondition = (index: number, value: string) => {
    const conditions = [...(step.config?.conditions || [])]
    conditions[index] = value
    updateConfig('conditions', conditions)
  }

  const removeCondition = (index: number) => {
    const conditions = step.config?.conditions || []
    updateConfig('conditions', conditions.filter((_, i) => i !== index))
  }

  const renderLLMCallConfig = () => (
    <div className="space-y-4">
      <ModelSelector 
        value={step.config?.model || ''}
        onValueChange={(value) => updateConfig('model', value)}
        filter="chat"
      />

      <div>
        <Label htmlFor="temperature">Temperature</Label>
        <Input
          id="temperature"
          type="number"
          step="0.1"
          min="0"
          max="2"
          value={step.config?.temperature || 0.7}
          onChange={(e) => updateConfig('temperature', parseFloat(e.target.value))}
        />
      </div>

      <div>
        <Label htmlFor="max_tokens">Max Tokens</Label>
        <Input
          id="max_tokens"
          type="number"
          value={step.config?.max_tokens || 1000}
          onChange={(e) => updateConfig('max_tokens', parseInt(e.target.value))}
        />
      </div>

      <div>
        <div className="flex items-center justify-between mb-2">
          <Label>Messages</Label>
          <Button variant="outline" size="sm" onClick={addMessage}>
            <Plus className="h-3 w-3 mr-1" />
            Add Message
          </Button>
        </div>
        <div className="space-y-2">
          {(step.config?.messages || []).map((message: any, index: number) => (
            <Card key={index}>
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <Select 
                    value={message.role || 'user'} 
                    onValueChange={(value) => updateMessage(index, 'role', value)}
                  >
                    <SelectTrigger className="w-32">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="system">System</SelectItem>
                      <SelectItem value="user">User</SelectItem>
                      <SelectItem value="assistant">Assistant</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => removeMessage(index)}
                  >
                    <Trash2 className="h-3 w-3" />
                  </Button>
                </div>
                <Textarea
                  value={message.content || ''}
                  onChange={(e) => updateMessage(index, 'content', e.target.value)}
                  placeholder="Enter message content..."
                  rows={2}
                />
              </CardContent>
            </Card>
          ))}
          
          {(step.config?.messages || []).length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No messages added yet
            </p>
          )}
        </div>
      </div>

      <div>
        <Label htmlFor="output_variable">Output Variable</Label>
        <Input
          id="output_variable"
          value={step.config?.output_variable || ''}
          onChange={(e) => updateConfig('output_variable', e.target.value)}
          placeholder="Variable name to store the response"
        />
      </div>
    </div>
  )

  const renderChatbotConfig = () => (
    <div className="space-y-4">
      <div>
          <Label htmlFor="chatbot_id">Chatbot</Label>
          <Select value={step.config?.chatbot_id || ''} onValueChange={(value) => updateConfig('chatbot_id', value)}>
            <SelectTrigger>
              <SelectValue placeholder={
                availableChatbots.length > 0 
                  ? "Select a chatbot" 
                  : "No chatbots available"
              } />
            </SelectTrigger>
            <SelectContent>
              {availableChatbots.length > 0 ? (
                availableChatbots.map(chatbot => (
                  <SelectItem key={chatbot.id} value={chatbot.id}>
                    {/* Show human-readable names instead of IDs */}
                    {chatbot.name}
                  </SelectItem>
                ))
              ) : (
                <SelectItem value="" disabled>
                  No chatbots created yet
                </SelectItem>
              )}
            </SelectContent>
          </Select>
          {availableChatbots.length === 0 && (
            <p className="text-sm text-muted-foreground mt-1">
              Create chatbots in the Chatbot section to use them in workflows
            </p>
          )}
          {step.config?.chatbot_id && availableChatbots.length > 0 && (
            <p className="text-sm text-muted-foreground mt-1">
              Selected: {availableChatbots.find(c => c.id === step.config?.chatbot_id)?.name || 'Unknown'}
            </p>
          )}
        </div>

        <div>
          <Label htmlFor="message_template">Message Template</Label>
          <Textarea
            id="message_template"
            value={step.config?.message_template || ''}
            onChange={(e) => updateConfig('message_template', e.target.value)}
            placeholder="Enter message template with variables like {variable_name}"
            rows={3}
          />
        </div>

        <div className="flex items-center space-x-2">
          <Switch
            id="create_new_conversation"
            checked={step.config?.create_new_conversation || false}
            onCheckedChange={(checked) => updateConfig('create_new_conversation', checked)}
          />
          <Label htmlFor="create_new_conversation">Create New Conversation</Label>
        </div>

        <div>
          <Label htmlFor="conversation_id">Conversation ID Variable</Label>
          <Input
            id="conversation_id"
            value={step.config?.conversation_id || ''}
            onChange={(e) => updateConfig('conversation_id', e.target.value)}
            placeholder="Variable containing conversation ID"
          />
        </div>

        <div>
          <Label htmlFor="output_variable">Output Variable</Label>
          <Input
            id="output_variable"
            value={step.config?.output_variable || ''}
            onChange={(e) => updateConfig('output_variable', e.target.value)}
            placeholder="Variable name to store the response"
          />
        </div>
      </div>
    )

  const renderTransformConfig = () => (
    <div className="space-y-4">
      <div>
        <Label htmlFor="input_variable">Input Variable</Label>
        <Select value={step.config?.input_variable || ''} onValueChange={(value) => updateConfig('input_variable', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select input variable" />
          </SelectTrigger>
          <SelectContent>
            {availableVariables.map(variable => (
              <SelectItem key={variable} value={variable}>{variable}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label htmlFor="transformation">Transformation</Label>
        <Select value={step.config?.transformation || ''} onValueChange={(value) => updateConfig('transformation', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select transformation type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="extract:response">Extract Response</SelectItem>
            <SelectItem value="json_parse">Parse JSON</SelectItem>
            <SelectItem value="text_clean">Clean Text</SelectItem>
            <SelectItem value="uppercase">To Uppercase</SelectItem>
            <SelectItem value="lowercase">To Lowercase</SelectItem>
            <SelectItem value="trim">Trim Whitespace</SelectItem>
            <SelectItem value="custom">Custom Transformation</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {step.config?.transformation === 'custom' && (
        <div>
          <Label htmlFor="custom_code">Custom Transformation Code</Label>
          <Textarea
            id="custom_code"
            value={step.config?.custom_code || ''}
            onChange={(e) => updateConfig('custom_code', e.target.value)}
            placeholder="Enter transformation logic (Python code)"
            rows={5}
          />
        </div>
      )}

      <div>
        <Label htmlFor="output_variable">Output Variable</Label>
        <Input
          id="output_variable"
          value={step.config?.output_variable || ''}
          onChange={(e) => updateConfig('output_variable', e.target.value)}
          placeholder="Variable name to store the result"
        />
      </div>
    </div>
  )

  const renderConditionalConfig = () => (
    <div className="space-y-4">
      <div>
        <div className="flex items-center justify-between mb-2">
          <Label>Conditions</Label>
          <Button variant="outline" size="sm" onClick={addCondition}>
            <Plus className="h-3 w-3 mr-1" />
            Add Condition
          </Button>
        </div>
        <div className="space-y-2">
          {(step.config?.conditions || []).map((condition: string, index: number) => (
            <div key={index} className="flex items-center gap-2">
              <Input
                value={condition}
                onChange={(e) => updateCondition(index, e.target.value)}
                placeholder="e.g., {variable} == 'value'"
                className="flex-1"
              />
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8"
                onClick={() => removeCondition(index)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </div>
          ))}
          
          {(step.config?.conditions || []).length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-4">
              No conditions added yet
            </p>
          )}
        </div>
      </div>

      <div>
        <Label htmlFor="logic_operator">Logic Operator</Label>
        <Select value={step.config?.logic_operator || 'and'} onValueChange={(value) => updateConfig('logic_operator', value)}>
          <SelectTrigger>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="and">AND (all conditions must be true)</SelectItem>
            <SelectItem value="or">OR (any condition must be true)</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label htmlFor="true_output">True Output Variable</Label>
        <Input
          id="true_output"
          value={step.config?.true_output || ''}
          onChange={(e) => updateConfig('true_output', e.target.value)}
          placeholder="Variable to set when conditions are true"
        />
      </div>

      <div>
        <Label htmlFor="false_output">False Output Variable</Label>
        <Input
          id="false_output"
          value={step.config?.false_output || ''}
          onChange={(e) => updateConfig('false_output', e.target.value)}
          placeholder="Variable to set when conditions are false"
        />
      </div>
    </div>
  )

  const renderParallelConfig = () => (
    <div className="space-y-4">
      <div>
        <Label htmlFor="max_concurrent">Max Concurrent Steps</Label>
        <Input
          id="max_concurrent"
          type="number"
          min="1"
          max="10"
          value={step.config?.max_concurrent || 3}
          onChange={(e) => updateConfig('max_concurrent', parseInt(e.target.value))}
        />
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="wait_for_all"
          checked={step.config?.wait_for_all !== false}
          onCheckedChange={(checked) => updateConfig('wait_for_all', checked)}
        />
        <Label htmlFor="wait_for_all">Wait for All Steps to Complete</Label>
      </div>

      <div>
        <Label htmlFor="timeout">Timeout (seconds)</Label>
        <Input
          id="timeout"
          type="number"
          min="1"
          value={step.config?.timeout || 300}
          onChange={(e) => updateConfig('timeout', parseInt(e.target.value))}
        />
      </div>

      <div className="p-3 bg-muted rounded">
        <p className="text-sm text-muted-foreground">
          <strong>Note:</strong> Parallel steps are defined as sub-steps within this step. 
          Use the visual editor to configure the parallel execution flow.
        </p>
      </div>
    </div>
  )

  const renderRAGSearchConfig = () => (
    <div className="space-y-4">
      <div>
        <Label htmlFor="collection">RAG Collection</Label>
        <Select value={step.config?.collection || ''} onValueChange={(value) => updateConfig('collection', value)}>
          <SelectTrigger>
            <SelectValue placeholder="Select a collection" />
          </SelectTrigger>
          <SelectContent>
            {availableCollections.length > 0 ? (
              availableCollections.map(collection => (
                <SelectItem key={collection} value={collection}>{collection}</SelectItem>
              ))
            ) : (
              <SelectItem value="default_collection">Default Collection</SelectItem>
            )}
          </SelectContent>
        </Select>
      </div>

      <div>
        <Label htmlFor="query_template">Query Template</Label>
        <Textarea
          id="query_template"
          value={step.config?.query_template || ''}
          onChange={(e) => updateConfig('query_template', e.target.value)}
          placeholder="Enter search query with variables like {variable_name}"
          rows={2}
        />
      </div>

      <div>
        <Label htmlFor="top_k">Top K Results</Label>
        <Input
          id="top_k"
          type="number"
          min="1"
          max="50"
          value={step.config?.top_k || 5}
          onChange={(e) => updateConfig('top_k', parseInt(e.target.value))}
        />
      </div>

      <div>
        <Label htmlFor="score_threshold">Score Threshold</Label>
        <Input
          id="score_threshold"
          type="number"
          step="0.01"
          min="0"
          max="1"
          value={step.config?.score_threshold || 0.5}
          onChange={(e) => updateConfig('score_threshold', parseFloat(e.target.value))}
        />
      </div>

      <div>
        <Label htmlFor="output_variable">Output Variable</Label>
        <Input
          id="output_variable"
          value={step.config?.output_variable || ''}
          onChange={(e) => updateConfig('output_variable', e.target.value)}
          placeholder="Variable name to store the search results"
        />
      </div>
    </div>
  )

  const getStepIcon = (type: string) => {
    switch (type) {
      case 'llm_call': return <MessageSquare className="h-4 w-4" />
      case 'chatbot': return <MessageSquare className="h-4 w-4" />
      case 'transform': return <Zap className="h-4 w-4" />
      case 'conditional': return <GitBranch className="h-4 w-4" />
      case 'parallel': return <Move className="h-4 w-4" />
      case 'rag_search': return <Database className="h-4 w-4" />
      default: return <Settings className="h-4 w-4" />
    }
  }

  const renderStepConfig = () => {
    switch (step.type) {
      case 'llm_call': return renderLLMCallConfig()
      case 'chatbot': return renderChatbotConfig()
      case 'transform': return renderTransformConfig()
      case 'conditional': return renderConditionalConfig()
      case 'parallel': return renderParallelConfig()
      case 'rag_search': return renderRAGSearchConfig()
      default: 
        return (
          <div className="text-center py-8">
            <Settings className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
            <p className="text-sm text-muted-foreground">
              Configuration for step type "{step.type}" is not yet implemented.
            </p>
          </div>
        )
    }
  }

  return (
    <div className="space-y-4">
      {/* Step Header */}
      <div className="flex items-center gap-2">
        {getStepIcon(step.type)}
        <div>
          <h3 className="font-medium">{step.name}</h3>
          <Badge variant="secondary" className="text-xs">
            {step.type}
          </Badge>
        </div>
      </div>

      <Separator />

      {/* Basic Configuration */}
      <div>
        <Label htmlFor="step-name">Step Name</Label>
        <Input
          id="step-name"
          value={step.name}
          onChange={(e) => onUpdateStep(step.id, { name: e.target.value })}
          placeholder="Enter step name"
        />
      </div>

      <Separator />

      {/* Step-specific Configuration */}
      <div>
        <Label className="text-base font-medium">Configuration</Label>
        <div className="mt-3">
          {renderStepConfig()}
        </div>
      </div>

      {/* Variable Hints */}
      {availableVariables.length > 0 && (
        <>
          <Separator />
          <div>
            <Label className="text-sm font-medium">Available Variables</Label>
            <div className="flex flex-wrap gap-1 mt-2">
              {availableVariables.map(variable => (
                <Badge key={variable} variant="outline" className="text-xs">
                  {`{${variable}}`}
                </Badge>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}